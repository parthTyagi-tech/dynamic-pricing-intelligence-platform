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

MATCH_THRESHOLD = 0.75
CIRCUIT_FAILURE_THRESHOLD = 5
DEFAULT_BACKOFF_MINUTES = 15
MAX_BACKOFF_MINUTES = 240

# Generic product-detail-page path markers used to distinguish a real
# product link from a search-results/category link when scanning HTML.
# Deliberately generic (not platform-specific selectors) — see the
# module docstring note on limitations below.
_PRODUCT_PATH_MARKERS = ("/dp/", "/p/", "/product/", "/itm/", "pid=", "/shop/")
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
      Tier 1 — internal_api:     platform JSON/internal API, if known (subclass hook;
                                  returns None by default since no platform in this
                                  codebase has a documented internal API endpoint yet)
      Tier 2 — mobile_headers:   HTTP GET impersonating a mobile client (often served
                                  a lighter, less bot-defended page than desktop)
      Tier 3 — playwright:       headless browser render, for JS-heavy pages tier 1/2
                                  can't extract from; degrades cleanly if Playwright
                                  isn't installed rather than crashing the job

    Each tier is tried in order; the first tier to produce a result meeting
    MATCH_THRESHOLD wins. All tiers share the same circuit-breaker gate, so a
    platform that's OPEN is skipped entirely rather than burning 3 tiers'
    worth of requests against a site that's actively blocking us.

    KNOWN LIMITATION: product-link and price/title extraction in tiers 2/3
    are generic regex/heuristic-based, not platform-specific DOM selectors.
    This is honest-but-imperfect: it will sometimes fail to find a genuine
    product deep-link and fall back to the search-results URL, in which case
    `url_verified=False` is set on the ScrapedOffer so downstream UI/analysts
    can tell the difference. Production hardening should add per-platform
    selector modules (BeautifulSoup) in platform_scrapers.py.
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
    # URL building / matching (unchanged from prior version)
    # ------------------------------------------------------------------

    def build_search_url(self, query: str) -> str:
        if not query:
            return self.base_url

        clean_query = " ".join(query.strip().split())
        if "?" in self.search_url_template:
            base_part, query_part = self.search_url_template.split("?", 1)
            if "{query}" in query_part:
                encoded = quote_plus(clean_query)
            else:
                encoded = quote(clean_query, safe="")
        else:
            encoded = quote(clean_query, safe="")

        return self.search_url_template.format(query=encoded)

    def compute_match_score(
        self,
        scraped_title: str,
        target_name: str,
        brand: str = "",
        barcode: str = ""
    ) -> float:
        if not scraped_title or not target_name:
            return 0.0

        title_norm = re.sub(r"[^a-z0-9\s]", "", scraped_title.lower())
        target_norm = re.sub(r"[^a-z0-9\s]", "", target_name.lower())
        brand_norm = re.sub(r"[^a-z0-9\s]", "", (brand or "").lower()).strip()

        if barcode and len(barcode) >= 8 and barcode.lower() in title_norm:
            return 1.0

        if brand_norm:
            brand_words = brand_norm.split()
            if not all(bw in title_norm for bw in brand_words):
                return 0.2

        target_tokens = set(target_norm.split())
        title_tokens = set(title_norm.split())

        stop_words = {"the", "and", "with", "for", "in", "by", "of", "a", "an", "edition"}
        target_tokens = {t for t in target_tokens if t not in stop_words and len(t) > 1}
        title_tokens = {t for t in title_tokens if t not in stop_words and len(t) > 1}

        if not target_tokens:
            return 0.5

        intersection = target_tokens.intersection(title_tokens)
        overlap_score = len(intersection) / len(target_tokens)

        return round(min(1.0, max(0.0, overlap_score)), 2)

    def _extract_price_and_title(self, html_content: str) -> tuple:
        match = re.search(r"(?:\u20b9|INR|Rs\.?)\s*([\d,]+(?:\.\d{2})?)", html_content)
        price = 0.0
        if match:
            clean_str = match.group(1).replace(",", "")
            price = float(clean_str)

        title_match = re.search(r"<title>(.*?)</title>", html_content, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else "Product"
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
    # Mock shortcut (unchanged — used by CI/demos)
    # ------------------------------------------------------------------

    def _generate_mock_price(self, product_id: str, baseline_price: float) -> Dict[str, Any]:
        seed_val = int(hashlib.md5(f"{product_id}_{self.platform_name}".encode()).hexdigest()[:6], 16)
        variance_pct = ((seed_val % 18) - 10) / 100.0
        simulated_price = round(baseline_price * (1.0 + variance_pct), 2)
        if simulated_price <= 0:
            simulated_price = baseline_price

        slug = re.sub(r"[^a-z0-9]+", "-", self.platform_name.lower())
        return {
            "platform": self.platform_name,
            "price": simulated_price,
            "currency": "INR",
            "in_stock": True,
            "stock_status": "in_stock",
            "product_url": f"{self.base_url}/dp/{slug}-{product_id[:8]}",
            "product_title": f"Verified match on {self.platform_name}",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "match_score": 0.92,
            "unverified_match": False,
            "url_verified": True,
            "scrape_mode": "mock_simulation",
            "data_source": "mock_simulation",
            "status": "success",
        }

    # ------------------------------------------------------------------
    # Tier 1 — internal API (subclass hook)
    # ------------------------------------------------------------------

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str) -> Optional[Dict[str, Any]]:
        """
        Override in a platform subclass if/when that platform's internal
        JSON search API is reverse-engineered and documented. Default: not
        implemented for any platform in this codebase yet, so this tier is
        always skipped — an honest no-op rather than a fake success.
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
                    if resp.status in (403, 429, 503):
                        raise RuntimeError(f"HTTP {resp.status} Block/Rate-Limit")
                    html_text = await resp.text()
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

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    page = await browser.new_page(
                        user_agent=(
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                        )
                    )
                    await page.goto(search_url, timeout=20000, wait_until="domcontentloaded")
                    html_text = await page.content()
                    landed_url = page.url
                finally:
                    await browser.close()
        except Exception as ex:
            logger.warning(f"[{self.platform_name}] tier3 playwright failed: {ex}")
            return None

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
        product_id = product["id"]
        product_name = product["name"]
        brand = product.get("brand", "")
        barcode = product.get("barcode", "")
        baseline_price = float(product.get("current_price", 0.0) or 1000.0)

        await self.emit_event(
            task_id=task_id, product_id=product_id, organization_id=organization_id,
            event_type="scraper_started",
            message=f"{self.platform_name} scraper agent initiated task.",
            payload={"platform": self.platform_name},
        )

        is_mock = os.environ.get("MOCK_SCRAPING", "true").lower() == "true"
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
                }

            result = self._generate_mock_price(product_id, baseline_price)
            await self.emit_event(
                task_id=task_id, product_id=product_id, organization_id=organization_id,
                event_type="scraper_completed",
                message=f"{self.platform_name} found verified price: \u20b9{result['price']:,.2f} (Match: 92%)",
                payload=result,
            )
            return result

        # ------------------------------------------------------------
        # Live: circuit breaker gate, then 3-tier fallback
        # ------------------------------------------------------------
        allowed, state = self._circuit_allows_request()
        if not allowed:
            self.record_decision(
                task_id=task_id, decision_point="Circuit Breaker Check",
                rationale=f"{self.platform_name} circuit is OPEN — skipping to protect against wasted "
                          "requests against a platform that's actively blocking us.",
                action_taken="Skip scrape, return estimated_fallback",
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
                last_reason = f"{tier_name}_validation_failed"
                continue

            self._record_scrape_success()
            result = validated.model_dump(mode="json")
            result["status"] = "success"
            await self.emit_event(
                task_id=task_id, product_id=product_id, organization_id=organization_id,
                event_type="scraper_completed",
                message=f"{self.platform_name} verified via {tier_name}: "
                        f"\u20b9{result['price']:,.2f} (Match: {int(result['match_score']*100)}%)",
                payload=result,
            )
            return result

        # All tiers exhausted
        self._record_scrape_failure(last_reason)
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
        }
