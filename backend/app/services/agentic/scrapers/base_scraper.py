import asyncio
import hashlib
import logging
import os
import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, quote_plus, urljoin

from pydantic import ValidationError

from app.services.agentic.base_agent import BaseAgent
from app.services.agentic.scrapers.schemas import ScrapedOffer
from app.utils.security_guardrails import validate_outbound_url

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 0.70
CIRCUIT_FAILURE_THRESHOLD = 5
DEFAULT_BACKOFF_MINUTES = 15
MAX_BACKOFF_MINUTES = 240

# Negative accessory tokens: if the catalog product does NOT ask for an
# accessory but the candidate listing contains one, hard-disqualify with 0.20.
NEGATIVE_ACCESSORY_TOKENS = {
    "refill", "refills", "cartridge", "cartridges", "ink",
    "lead", "leads", "case", "cover", "pouch", "pack of",
    "set of", "bundle", "notebook", "eraser", "pencil"
}


class ScraperException(Exception):
    """Base exception for scraping operations."""
    pass


class PlatformRateLimitError(ScraperException):
    """Raised when a platform responds with HTTP 429 or explicit rate-limiting."""
    pass


class BotDetectionEncountered(ScraperException):
    """Raised when a platform responds with CAPTCHA, WAF challenge, or bot protection."""
    pass


# Generic product-detail-page path markers used to distinguish a real
# product link from a search-results/category link when scanning HTML.
_PRODUCT_PATH_MARKERS = ("/dp/", "/p/", "/product/", "/itm/", "pid=", "/shop/", "/prn/")
_HREF_RE = re.compile(r'href="([^"]+)"', re.IGNORECASE)


class ProxyManager:
    """
    Gap #5 & SEC-12: Proxy Pool Manager with credential masking.
    Rotates proxies to evade rate-limits and IP-level bans.
    """

    def __init__(self):
        proxy_env = os.environ.get("SCRAPER_PROXIES", "")
        self.proxies = [p.strip() for p in proxy_env.split(",") if p.strip()]
        self._index = 0

    def get_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        proxy = self.proxies[self._index % len(self.proxies)]
        self._index += 1
        return proxy

    def mask_proxy(self, proxy_str: Optional[str]) -> str:
        """SEC-12: Never log plaintext proxy credentials."""
        if not proxy_str:
            return "direct_connection"
        return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", proxy_str)


class BaseScraperAgent(BaseAgent):
    """
    Autonomous Scraper Agent with a 3-tier fallback strategy:
      Tier 1 — internal_api:     platform JSON/internal API, if known
      Tier 2 — mobile_headers:   HTTP GET impersonating a mobile/desktop client
      Tier 3 — playwright:       headless browser render for JS-heavy pages
    """

    def __init__(self, platform_name: str, search_url_template: str, base_url: str):
        super().__init__(
            role=f"{platform_name}ScraperAgent",
            goal=f"Extract verified live price and availability for products on {platform_name}",
            available_tools=["internal_api", "mobile_headers", "playwright_browser", "proxy_rotation"],
        )
        self.platform_name = platform_name
        self.search_url_template = search_url_template
        self.base_url = base_url
        self.proxy_manager = ProxyManager()

    # ------------------------------------------------------------------
    # URL building / matching (Dynamic Jaccard + Brand Check)
    # ------------------------------------------------------------------

    def build_search_url(self, query: str) -> str:
        if not query:
            return self.base_url

        # Clean any leading single quotes or formula prefixes neutralized during CSV imports
        cleaned = re.sub(r"^['\"=\+\-@]+(?:\w+\(.*?\)|cmd\|.*?!A\d+|[\d\*\+\-/]+)?\s*", "", query.strip()).strip()
        clean_query = " ".join((cleaned or query).split())
        if "?" in self.search_url_template:
            base_part, query_part = self.search_url_template.split("?", 1)
            if "{query}" in query_part:
                encoded = quote_plus(clean_query)
            else:
                encoded = quote(clean_query, safe="")
        else:
            encoded = quote(clean_query, safe="")

        return self.search_url_template.format(query=encoded)

    def check_bot_detection(self, status_code: int, html_text: str = "") -> None:
        """
        Detects bot protection, rate limits, and CAPTCHAs.
        Raises PlatformRateLimitError or BotDetectionEncountered.
        """
        if status_code == 429:
            raise PlatformRateLimitError(f"HTTP 429 Rate Limit on {self.platform_name}")

        lower_html = (html_text or "").lower()
        if status_code in (403, 503):
            if any(term in lower_html for term in ["captcha", "challenge", "verify you are human", "robot", "datadome", "cloudflare", "perimeterx", "automated access"]):
                raise BotDetectionEncountered(f"Bot detection challenge (HTTP {status_code}) on {self.platform_name}")
            raise BotDetectionEncountered(f"Access forbidden/unavailable (HTTP {status_code}) on {self.platform_name}")

        if lower_html:
            if "api-services-support@amazon.com" in lower_html or "validatecaptcha" in lower_html or "type the characters you see in this image" in lower_html:
                raise BotDetectionEncountered(f"Amazon CAPTCHA detected on {self.platform_name}")
            if "cf-browser-verification" in lower_html or "cf-turnstile" in lower_html:
                raise BotDetectionEncountered(f"Cloudflare challenge detected on {self.platform_name}")

    def compute_match_score(
        self,
        scraped_title: str,
        target_name: str,
        brand: str = "",
        barcode: str = "",
        catalog_price: float = 0.0,
        scraped_price: float = 0.0
    ) -> float:
        """
        Anti-accessory match verification gate with brand gating and price anomaly detection.
        - Hard 0.20 penalty for negative accessory tokens (refill, ink, lead, etc.)
        - 50% brand-absence discount.
        - Token coverage + Jaccard weighting (0.75 * coverage + 0.25 * jaccard).
        - Price ratio anomaly guardrail (< 0.35x or > 3.0x baseline → cap at 0.40).
        - Barcode exact match yields 1.0.
        """
        if not scraped_title or not target_name:
            return 0.0

        title_norm = re.sub(r"[^a-z0-9\s]", "", scraped_title.lower())
        target_norm = re.sub(r"[^a-z0-9\s]", "", target_name.lower())
        brand_norm = re.sub(r"[^a-z0-9\s]", "", (brand or "").lower()).strip()

        # Barcode exact match
        if barcode and len(barcode) >= 8 and barcode.lower() in title_norm:
            return 1.0

        # 1. Hard Accessory Disqualification Gate
        # If the catalog product does NOT ask for an accessory but the candidate
        # listing contains one, disqualify immediately with 0.20 (below 0.70 threshold).
        target_has_accessory = any(token in target_norm for token in NEGATIVE_ACCESSORY_TOKENS)
        candidate_has_accessory = any(token in title_norm for token in NEGATIVE_ACCESSORY_TOKENS)
        if candidate_has_accessory and not target_has_accessory:
            return 0.20

        # 2. Normalization of common compound terms & synonyms
        title_norm = title_norm.replace("ball point", "ballpoint").replace("air press", "airpress")
        target_norm = target_norm.replace("ball point", "ballpoint").replace("air press", "airpress")

        # Feature synonym mapping for pressurized technology
        if "technology" in title_norm and "pressurized" in target_norm:
            title_norm = title_norm.replace("technology", "pressurized")
        if "compressed" in title_norm and "pressurized" in target_norm:
            title_norm = title_norm.replace("compressed", "pressurized")

        # 3. Clean Jaccard Token Overlap with Stop-Word Removal
        stop_words = {"the", "and", "with", "for", "in", "by", "of", "a", "an", "edition", "set", "pack", "series", "brand", "color", "new"}
        target_tokens = {t for t in target_norm.split() if t not in stop_words and len(t) > 1}
        title_tokens = {t for t in title_norm.split() if t not in stop_words and len(t) > 1}

        if not target_tokens or not title_tokens:
            return 0.0

        intersection = target_tokens.intersection(title_tokens)
        union = target_tokens.union(title_tokens)

        target_coverage = len(intersection) / len(target_tokens)
        raw_jaccard = len(intersection) / len(union) if union else 0.0

        # Weighted combination: rewards listings containing all target keywords
        # without penalizing verbose e-commerce titles
        match_score = (0.75 * target_coverage) + (0.25 * raw_jaccard)

        # 4. Brand presence check: 50% discount if brand specified but absent
        if brand_norm:
            brand_tokens = [b for b in brand_norm.split() if len(b) > 1 and b not in stop_words]
            if brand_tokens:
                brand_present = any(b in title_norm for b in brand_tokens)
                if not brand_present:
                    match_score *= 0.5

        # 5. Price Ratio Anomaly Guardrail
        if catalog_price > 0 and scraped_price > 0:
            if scraped_price < (catalog_price * 0.35) or scraped_price > (catalog_price * 3.0):
                match_score = min(match_score, 0.40)

        return round(min(1.0, max(0.0, match_score)), 2)

    def _extract_price_and_title(self, html_content: str) -> tuple:
        """Extracts price, title, and optional mrp from raw HTML."""
        title = "Product"
        price = 0.0

        # Try BeautifulSoup for clean DOM parsing
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")
            title_node = soup.find("title")
            if title_node and title_node.text:
                title = title_node.text.strip()
        except Exception:
            title_match = re.search(r"<title>(.*?)</title>", html_content, re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()

        match = re.search(r"(?:\u20b9|INR|Rs\.?)\s*([\d,]+(?:\.\d{2})?)", html_content)
        if match:
            clean_str = match.group(1).replace(",", "")
            try:
                price = float(clean_str)
            except ValueError:
                price = 0.0

        return price, title

    def _extract_product_link(self, html_content: str, fallback_url: str) -> Tuple[str, bool]:
        """
        Best-effort extraction of a genuine product-detail link from a
        search-results page, so `product_url` points at the actual listing
        an analyst should click through to, not just the search query.

        Returns (url, url_verified). Falls back to `fallback_url` (the
        search page) with url_verified=False if no candidate is found or
        the candidate fails the SEC-12 outbound-URL check.
        """
        for href in _HREF_RE.findall(html_content):
            if not any(marker in href for marker in _PRODUCT_PATH_MARKERS):
                continue
            candidate = urljoin(self.base_url, href)
            try:
                validate_outbound_url(candidate)
            except ValueError:
                continue
            return candidate, True

        return fallback_url, False

    # ------------------------------------------------------------------
    # Circuit breaker (SEC-aligned: fail closed, never hang the job)
    # ------------------------------------------------------------------

    def _get_reliability_record(self):
        from app.extensions import db
        from app.models.scraper_reliability import ScraperReliability

        rel = ScraperReliability.query.get(self.platform_name)
        if rel is None:
            rel = ScraperReliability(platform=self.platform_name)
            db.session.add(rel)
            db.session.commit()
        return rel

    def _circuit_allows_request(self) -> Tuple[bool, str]:
        """Returns (allowed, state_label)."""
        from app.extensions import db
        from app.models.scraper_reliability import CircuitState

        rel = self._get_reliability_record()
        now = datetime.now(timezone.utc)

        if rel.circuit_state == CircuitState.OPEN:
            opened_at = rel.circuit_opened_at or now
            if opened_at.tzinfo is None:
                opened_at = opened_at.replace(tzinfo=timezone.utc)
            elapsed_minutes = (now - opened_at).total_seconds() / 60.0
            backoff = rel.backoff_minutes or DEFAULT_BACKOFF_MINUTES
            if elapsed_minutes >= backoff:
                rel.circuit_state = CircuitState.HALF_OPEN
                db.session.commit()
                return True, "half_open_probe"
            return False, "circuit_open"

        return True, rel.circuit_state

    def _record_scrape_success(self) -> None:
        from app.extensions import db
        from app.models.scraper_reliability import CircuitState

        rel = self._get_reliability_record()
        rel.failure_count_last_hour = 0
        rel.circuit_state = CircuitState.CLOSED
        rel.circuit_opened_at = None
        rel.backoff_minutes = DEFAULT_BACKOFF_MINUTES
        rel.last_successful_scrape_at = datetime.now(timezone.utc)
        db.session.commit()

    def _record_scrape_failure(self, reason: str) -> None:
        from app.extensions import db
        from app.models.scraper_reliability import CircuitState

        rel = self._get_reliability_record()
        rel.failure_count_last_hour = (rel.failure_count_last_hour or 0) + 1
        rel.last_failure_at = datetime.now(timezone.utc)
        rel.last_failure_reason = str(reason)[:255]

        if rel.circuit_state == CircuitState.HALF_OPEN:
            # The recovery probe itself failed — re-open with extended
            # backoff (capped) instead of hammering a still-blocking site.
            rel.circuit_state = CircuitState.OPEN
            rel.circuit_opened_at = datetime.now(timezone.utc)
            rel.backoff_minutes = min((rel.backoff_minutes or DEFAULT_BACKOFF_MINUTES) * 2, MAX_BACKOFF_MINUTES)
        elif rel.failure_count_last_hour >= CIRCUIT_FAILURE_THRESHOLD:
            rel.circuit_state = CircuitState.OPEN
            rel.circuit_opened_at = datetime.now(timezone.utc)

        db.session.commit()

    # ------------------------------------------------------------------
    # Mock shortcut (used strictly when MOCK_SCRAPING=true in tests)
    # ------------------------------------------------------------------

    def _generate_mock_price(self, product_id: str, baseline_price: float, product_name: str = "", brand: str = "") -> Dict[str, Any]:
        seed_val = int(hashlib.md5(f"{product_id}_{self.platform_name}".encode()).hexdigest()[:6], 16)
        variance_pct = ((seed_val % 18) - 10) / 100.0
        simulated_price = round(baseline_price * (1.0 + variance_pct), 2)
        if simulated_price <= 0:
            simulated_price = baseline_price

        slug = re.sub(r"[^a-z0-9]+", "-", self.platform_name.lower())
        mrp = round(simulated_price * 1.12, 2)
        simulated_title = f"{brand} {product_name}".strip() if (brand or product_name) else f"Verified match on {self.platform_name}"
        calculated_match = self.compute_match_score(simulated_title, product_name or "Product", brand=brand) if product_name else 0.85
        if calculated_match < 0.60:
            calculated_match = 0.82

        return {
            "platform": self.platform_name,
            "price": simulated_price,
            "mrp": mrp,
            "currency": "INR",
            "in_stock": True,
            "stock_status": "in_stock",
            "product_url": f"{self.base_url}/dp/{slug}-{product_id[:8]}",
            "product_title": self.sanitize_output(simulated_title),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "match_score": calculated_match,
            "unverified_match": False,
            "url_verified": True,
            "scrape_mode": "mock_simulation",
            "data_source": "mock_simulation",
            "status": "success",
            "latency_ms": 320.0,
        }

    # ------------------------------------------------------------------
    # Tier 1 — internal API (subclass hook)
    # ------------------------------------------------------------------

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Override in a platform subclass if/when that platform's internal
        JSON search API is reverse-engineered and documented.
        """
        return None

    # ------------------------------------------------------------------
    # Tier 2 — mobile headers HTTP fetch
    # ------------------------------------------------------------------

    async def _tier2_mobile_headers(
        self, task_id: str, product_id: str, organization_id: str,
        product_name: str, brand: str, barcode: str, proxy: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        import aiohttp

        search_url = self.build_search_url(f"{brand} {product_name}".strip())
        try:
            validate_outbound_url(search_url)
        except ValueError as ex:
            logger.warning(f"[{self.platform_name}] tier2 refused unsafe URL: {ex}")
            return None

        mobile_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
            ),
            "Accept-Language": "en-IN,en;q=0.9",
        }
        timeout = aiohttp.ClientTimeout(total=15)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(search_url, headers=mobile_headers, proxy=proxy) as resp:
                    html_text = await resp.text()
                    self.check_bot_detection(resp.status, html_text)
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            logger.warning(f"[{self.platform_name}] tier2 anti-bot / rate-limit encountered: {bde}")
            raise bde
        except Exception as ex:
            logger.warning(f"[{self.platform_name}] tier2 mobile_headers failed: {ex}")
            return None

        price, title = self._extract_price_and_title(html_text)
        match_score = self.compute_match_score(title, product_name, brand, barcode)
        if match_score < MATCH_THRESHOLD or price <= 0:
            return None

        product_url, url_verified = self._extract_product_link(html_text, fallback_url=search_url)

        return {
            "platform": self.platform_name,
            "price": price,
            "currency": "INR",
            "in_stock": True,
            "product_url": product_url,
            "url_verified": url_verified,
            "product_title": self.sanitize_output(title),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "match_score": match_score,
            "unverified_match": False,
            "scrape_mode": "mobile_headers",
            "data_source": "live_scrape",
        }

    # ------------------------------------------------------------------
    # Tier 3 — Playwright headless browser
    # ------------------------------------------------------------------

    async def _tier3_playwright(
        self, task_id: str, product_id: str, organization_id: str,
        product_name: str, brand: str, barcode: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.info(f"[{self.platform_name}] tier3 skipped: playwright not installed")
            return None

        search_url = self.build_search_url(f"{brand} {product_name}".strip())
        try:
            validate_outbound_url(search_url)
        except ValueError as ex:
            logger.warning(f"[{self.platform_name}] tier3 refused unsafe URL: {ex}")
            return None

        # Memory-safe Playwright lifecycle: explicit try/finally with pw.stop()
        # to prevent orphaned Chromium zombie processes during batch execution.
        pw_instance = None
        browser = None
        try:
            pw_instance = await async_playwright().start()
            browser = await pw_instance.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox",
                      "--disable-dev-shm-usage", "--disable-gpu"]
            )
            page = await browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-IN"
            )
            await page.goto(search_url, timeout=25000, wait_until="domcontentloaded")
            html_text = await page.content()
            landed_url = page.url
            self.check_bot_detection(200, html_text)
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            logger.warning(f"[{self.platform_name}] tier3 anti-bot detected: {bde}")
            raise bde
        except Exception as ex:
            logger.warning(f"[{self.platform_name}] tier3 playwright failed: {ex}")
            return None
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            if pw_instance:
                try:
                    await pw_instance.stop()
                except Exception:
                    pass

        price, title = self._extract_price_and_title(html_text)
        match_score = self.compute_match_score(title, product_name, brand, barcode)
        if match_score < MATCH_THRESHOLD or price <= 0:
            return None

        product_url, url_verified = self._extract_product_link(html_text, fallback_url=landed_url)

        return {
            "platform": self.platform_name,
            "price": price,
            "currency": "INR",
            "in_stock": True,
            "product_url": product_url,
            "url_verified": url_verified,
            "product_title": self.sanitize_output(title),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "match_score": match_score,
            "unverified_match": False,
            "scrape_mode": "playwright",
            "data_source": "live_scrape",
        }

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    async def scrape(
        self,
        task_id: str,
        product: Dict[str, Any],
        organization_id: str,
        simulate_failure: bool = False
    ) -> Dict[str, Any]:
        import time

        product_id = product["id"]
        product_name = product["name"]
        brand = product.get("brand", "")
        barcode = product.get("barcode", "")
        baseline_price = float(product.get("current_price", 0.0) or 1000.0)
        start_time = time.perf_counter()

        await self.emit_event(
            task_id=task_id, product_id=product_id, organization_id=organization_id,
            event_type="scraper_started",
            message=f"{self.platform_name} scraper agent initiated task.",
            payload={"platform": self.platform_name},
        )

        is_mock = os.environ.get("MOCK_SCRAPING", "false").lower() == "true"
        if is_mock:
            await asyncio.sleep(0.3)
            if simulate_failure:
                self.record_decision(
                    task_id=task_id, decision_point="Scrape Attempt",
                    rationale=f"Simulated live block encountered on {self.platform_name}.",
                    action_taken="Fail with unreachable status",
                )
                await self.emit_event(
                    task_id=task_id, product_id=product_id, organization_id=organization_id,
                    event_type="scraper_failed",
                    message=f"{self.platform_name} was blocked or returned no verified matches.",
                    payload={"platform": self.platform_name, "reason": "simulated_block"},
                )
                return {
                    "platform": self.platform_name, "status": "unreachable",
                    "reason": "simulated_block", "match_score": 0.0,
                    "unverified_match": True, "data_source": "estimated_fallback",
                    "latency_ms": 300.0,
                }

            result = self._generate_mock_price(product_id, baseline_price, product_name=product_name, brand=brand)
            await self.emit_event(
                task_id=task_id, product_id=product_id, organization_id=organization_id,
                event_type="scraper_completed",
                message=f"{self.platform_name} found verified price: ₹{result['price']:,.2f} (Match: {int(result['match_score']*100)}%)",
                payload=result,
            )
            return result

        # ------------------------------------------------------------
        # Live: circuit breaker gate, then 3-tier fallback
        # ------------------------------------------------------------
        allowed, state = self._circuit_allows_request()
        if not allowed:
            self.record_decision(
                task_id=task_id, decision_point="Marketplace Sensor Health",
                rationale=f"Platform {self.platform_name} circuit is temporarily OPEN with backoff remaining.",
                action_taken=f"Bypassed {self.platform_name} to preserve proxy pool and avoid rate limits",
            )
            await self.emit_event(
                task_id=task_id, product_id=product_id, organization_id=organization_id,
                event_type="scraper_failed",
                message=f"{self.platform_name} circuit breaker is open; skipping this run.",
                payload={"platform": self.platform_name, "reason": "circuit_open"},
            )
            return {
                "platform": self.platform_name, "status": "circuit_open",
                "reason": "circuit_open", "match_score": 0.0,
                "unverified_match": True, "data_source": "estimated_fallback",
                "latency_ms": 1.0,
            }

        proxy = self.proxy_manager.get_proxy()
        tiers = [
            ("internal_api", lambda: self._tier1_internal_api(product_name, brand, barcode)),
            ("mobile_headers", lambda: self._tier2_mobile_headers(
                task_id, product_id, organization_id, product_name, brand, barcode, proxy)),
            ("playwright", lambda: self._tier3_playwright(
                task_id, product_id, organization_id, product_name, brand, barcode)),
        ]

        last_reason = "no_tier_produced_a_verified_match"
        for tier_name, tier_fn in tiers:
            self.record_decision(
                task_id=task_id, decision_point=f"Tier: {tier_name}",
                rationale=f"Attempting {tier_name} via proxy {self.proxy_manager.mask_proxy(proxy)}",
                action_taken=f"Invoke {tier_name} for {self.platform_name}",
            )
            try:
                raw_result = await tier_fn()
            except (PlatformRateLimitError, BotDetectionEncountered) as bde:
                last_reason = str(bde)
                logger.warning(f"[{self.platform_name}] tier {tier_name} stopped by bot defense: {bde}")
                if tier_name != "playwright":
                    continue
                break  # Don't hammer further tiers if bot defense detected on playwright
            except Exception as ex:
                logger.warning(f"[{self.platform_name}] tier {tier_name} raised: {ex}")
                last_reason = f"{tier_name}_exception: {ex}"
                continue

            if raw_result is None:
                last_reason = f"{tier_name}_no_match"
                continue

            try:
                validated = ScrapedOffer(**raw_result)
            except ValidationError as ve:
                logger.warning(f"[{self.platform_name}] tier {tier_name} produced invalid offer: {ve}")
                last_reason = f"{tier_name}_validation_failed: {ve}"
                continue

            result = validated.model_dump(mode="json")
            latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
            result["latency_ms"] = latency_ms

            # Price ratio sanity bound: verify scraped price is within [0.4x, 2.5x] of catalog price
            price_val = float(result.get("price") or 0.0)
            if baseline_price > 0 and price_val > 0:
                ratio = price_val / baseline_price
                if ratio < 0.4 or ratio > 2.5:
                    logger.warning(
                        f"[{self.platform_name}] Scraped price ₹{price_val:.2f} is outside safe ratio "
                        f"[0.4x, 2.5x] of catalog price ₹{baseline_price:.2f} (ratio: {ratio:.2f}). "
                        "Quarantining as unverified_match."
                    )
                    result["unverified_match"] = True
                    result["data_source"] = "estimated_fallback"
                    result["status"] = "unverified"
                    result["match_score"] = min(float(result.get("match_score", 0.5)), 0.40)
                    last_reason = f"price_out_of_bounds_ratio_{ratio:.2f}"
                    continue

            self._record_scrape_success()
            result["status"] = "success"
            await self.emit_event(
                task_id=task_id, product_id=product_id, organization_id=organization_id,
                event_type="scraper_completed",
                message=f"{self.platform_name} verified via {tier_name}: "
                        f"₹{result['price']:,.2f} (Match: {int(result['match_score']*100)}%)",
                payload=result,
            )
            return result

        # All tiers exhausted or blocked
        self._record_scrape_failure(last_reason)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
        await self.emit_event(
            task_id=task_id, product_id=product_id, organization_id=organization_id,
            event_type="scraper_failed",
            message=f"{self.platform_name} failed across all tiers: {last_reason}",
            payload={"platform": self.platform_name, "error": last_reason},
        )
        return {
            "platform": self.platform_name, "status": "unreachable",
            "reason": last_reason, "match_score": 0.0,
            "unverified_match": True, "data_source": "estimated_fallback",
            "latency_ms": latency_ms,
        }
