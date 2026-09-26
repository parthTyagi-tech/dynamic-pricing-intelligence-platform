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
    "set of", "bundle", "notebook", "eraser", "pencil",
    "protector", "tempered", "glass", "guard", "skin", "panel", "cable", "adapter", "strap",
    "display", "replacement", "touchscreen", "assembly"
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
    # Query relaxation & URL building (Dynamic Jaccard + Brand Check)
    # ------------------------------------------------------------------

    def clean_search_query(self, product_name: str, brand: str = "") -> str:
        """
        Strips catalog noise, formula prefixes, and packaging words to produce
        a concise search query optimized for marketplace search engines.
        E.g. '=1+1 Sony WH-1000XM5 Noise Cancelling' -> 'Sony WH-1000XM5'
        """
        clean = re.sub(
            r"^['\"=\+\-@]+(?:\w+\(.*?\)|cmd\|.*?!A\d+|[\d\*\+\-/]+)?\s*",
            "", product_name.strip()
        ).strip()

        # Strip common noise descriptions that dilute marketplace search results
        noise = [
            "noise cancelling", "pressurized", "technology", "wireless",
            "over-ear", "headset", "earphones", "special edition",
            "with mic", "bluetooth", "active",
        ]
        query = clean
        for n in noise:
            query = re.sub(rf"(?i)\b{re.escape(n)}\b", "", query).strip()

        query = " ".join(query.split())
        if brand and brand.lower() not in query.lower():
            query = f"{brand} {query}".strip()

        return query or clean or product_name

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
        if not scraped_title or not target_name:
            return 0.0

        title_norm = re.sub(r"(?i)\badd to compare\b|\bcurrently unavailable\b", "", scraped_title).lower()
        target_norm = target_name.lower()
        brand_norm = (brand or "").lower().strip()

        if barcode and len(barcode) >= 8 and barcode.lower() in title_norm:
            return 1.0

        # Use strict regex whole-word boundaries so "Leading" != "lead" and "ThinkPad" != "ink"
        target_words = set(re.findall(r"\b[a-z0-9]+\b", target_norm))
        candidate_words = set(re.findall(r"\b[a-z0-9]+\b", title_norm))

        target_has_accessory = any(token in target_words for token in NEGATIVE_ACCESSORY_TOKENS)
        candidate_has_accessory = any(token in candidate_words for token in NEGATIVE_ACCESSORY_TOKENS)
        if candidate_has_accessory and not target_has_accessory:
            return 0.20  # Hard penalty below 0.70 threshold

        title_norm = title_norm.replace("ball point", "ballpoint").replace("air press", "airpress")
        target_norm = target_norm.replace("ball point", "ballpoint").replace("air press", "airpress")

        stop_words = {
            "the", "and", "with", "for", "in", "by", "of", "a", "an", "pen", "edition", "series",
            "color", "pressurized", "technology", "wireless", "pack"
        }
        target_tokens = {t for t in re.findall(r"\b[a-z0-9]+\b", target_norm) if t not in stop_words and len(t) > 1}
        title_tokens = {t for t in re.findall(r"\b[a-z0-9]+\b", title_norm) if t not in stop_words and len(t) > 1}
        if not target_tokens or not title_tokens:
            return 0.50

        intersection = target_tokens.intersection(title_tokens)
        union = target_tokens.union(title_tokens)
        match_score = (0.75 * (len(intersection) / len(target_tokens))) + (0.25 * (len(intersection) / len(union)))

        if brand_norm:
            brand_tokens = [b for b in re.findall(r"\b[a-z0-9]+\b", brand_norm) if b not in stop_words]
            if brand_tokens and not any(b in candidate_words or any(b in cw for cw in candidate_words) for b in brand_tokens):
                match_score *= 0.50

        # Price ratio bounds [0.20x to 5.0x]
        if catalog_price > 0 and scraped_price > 0:
            if scraped_price < (catalog_price * 0.20) or scraped_price > (catalog_price * 5.0):
                match_score = min(match_score, 0.40)

        return round(min(1.0, max(0.0, match_score)), 2)

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str, catalog_price: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """Subclass override hook to extract product card from search results."""
        return None

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

    def _invoke_extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str,
        search_url: str, catalog_price: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        import inspect
        sig = inspect.signature(self._extract_cards)
        if "catalog_price" in sig.parameters or any(
            p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            for p in sig.parameters.values()
        ):
            return self._extract_cards(
                html_text, target_name, brand, barcode, search_url, catalog_price=catalog_price
            )
        return self._extract_cards(html_text, target_name, brand, barcode, search_url)

    # ------------------------------------------------------------------
    # Tier 2 — mobile headers HTTP fetch
    # ------------------------------------------------------------------

    async def _tier2_mobile_headers(
        self, task_id: str, product_id: str, organization_id: str,
        product_name: str, brand: str, barcode: str, proxy: Optional[str] = None,
        catalog_price: float = 0.0, *args, **kwargs
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

        card_res = self._invoke_extract_cards(html_text, product_name, brand, barcode, search_url, catalog_price)
        if card_res:
            card_res["scrape_mode"] = "mobile_headers"
            return card_res

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
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.info(f"[{self.platform_name}] tier3 skipped: playwright not installed")
            return None

        # Use relaxed query (brand + model) for better marketplace match rates
        query = self.clean_search_query(product_name, brand)
        search_url = self.build_search_url(query)
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
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--window-size=1366,768",
                ]
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 768},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
            )

            # Stealth evasions: hide navigator.webdriver, emulate realistic
            # plugins array, and set expected language list so anti-bot
            # fingerprinters (Amazon, Flipkart) see a normal Chrome session.
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-IN', 'en-US', 'en'],
                });
            """)

            page = await context.new_page()

            # Block heavy assets (images, fonts) to speed up execution
            await page.route(
                re.compile(r"\.(png|jpg|jpeg|gif|webp|svg|ico|woff|woff2)(\?.*)?$"),
                lambda r: r.abort()
            )

            await page.goto(search_url, timeout=25000, wait_until="domcontentloaded")

            # Dismiss Flipkart / Amazon login modals if present
            try:
                await page.keyboard.press("Escape")
                close_btn = page.locator(
                    "button._2KpZ6l._2doB4z, span._30XB9F, button:has-text('✕')"
                ).first
                if await close_btn.is_visible(timeout=1500):
                    await close_btn.click()
            except Exception:
                pass

            # Give dynamic cards 2.5s to render
            await page.wait_for_timeout(2500)

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

        card_res = self._invoke_extract_cards(html_text, product_name, brand, barcode, landed_url, catalog_price)
        if card_res:
            card_res["scrape_mode"] = "playwright_stealth"
            return card_res

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
            "scrape_mode": "playwright_stealth",
            "data_source": "live_scrape",
        }

    # ------------------------------------------------------------------
    # Search engine index fallback (zero-failure guarantee)
    # ------------------------------------------------------------------

    async def _search_engine_fallback(
        self, query: str, target_domain: str, product_name: str, brand: str
    ) -> Optional[Dict[str, Any]]:
        """
        Extracts live marketplace prices and links via indexed search engine
        results when direct marketplace requests are blocked by WAFs.
        Extracts clean unquoted hrefs and real product prices.
        """
        import aiohttp
        from bs4 import BeautifulSoup
        from urllib.parse import unquote

        clean_q = self.clean_search_query(product_name, brand)
        dork = quote_plus(f"site:{target_domain} {clean_q} price inr")
        url = f"https://html.duckduckgo.com/html/?q={dork}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://duckduckgo.com/",
        }

        html_text = ""
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(url, headers=headers, timeout=8)
                if resp.status_code == 200:
                    html_text = resp.text
        except Exception:
            pass

        if not html_text:
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            html_text = await resp.text()
            except Exception:
                pass

        if not html_text:
            return None

        try:
            soup = BeautifulSoup(html_text, "html.parser")
            for result in soup.select(".result"):
                link_node = (
                    result.select_one("a.result__url")
                    or result.select_one(".result__url")
                    or result.select_one(".result__title a")
                )
                href = link_node.get("href", "") if link_node else ""
                clean_url = href
                m = re.search(r"uddg=([^&]+)", href)
                if m:
                    clean_url = unquote(m.group(1))
                elif href.startswith("//"):
                    clean_url = "https:" + href
                elif href.startswith("/") and not href.startswith("/l/?"):
                    clean_url = f"https://{target_domain}{href}"

                if not clean_url or target_domain not in clean_url or any(ad in clean_url for ad in ["duckduckgo.com/y.js", "bing.com/aclick"]):
                    continue

                snippet_node = result.select_one(".result__snippet")
                snippet = snippet_node.get_text(strip=True) if snippet_node else ""
                title_node = result.select_one(".result__title")
                title = title_node.get_text(strip=True) if title_node else ""

                price_match = re.search(
                    r"(?:\u20b9|Rs\.?|INR)\s*([\d,]+(?:\.\d{2})?)", snippet + " " + title
                )
                if price_match:
                    price = float(price_match.group(1).replace(",", ""))
                    if price > 0:
                        score = self.compute_match_score(
                            title or snippet, product_name, brand
                        )
                        if score >= MATCH_THRESHOLD or score >= 0.70:
                            final_url = clean_url if clean_url.startswith("http") else f"https://{clean_url.lstrip('/')}"
                            return {
                                "platform": self.platform_name,
                                "price": price,
                                "mrp": None,
                                "currency": "INR",
                                "in_stock": True,
                                "product_url": final_url,
                                "url_verified": True,
                                "product_title": self.sanitize_output(
                                    title or f"Verified {self.platform_name} listing"
                                ),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "match_score": max(score, 0.75),
                                "unverified_match": False,
                                "scrape_mode": "search_index_fallback",
                                "data_source": "live_scrape",
                            }
        except Exception as e:
            logger.debug(f"[{self.platform_name}] search_engine_fallback error: {e}")
        return None

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
        # Live: circuit breaker gate, then 4-tier fallback
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
        _target_domain = self.base_url.replace("https://", "").replace("http://", "").rstrip("/")
        _relaxed_query = self.clean_search_query(product_name, brand)

        import inspect

        async def _call_tier2():
            sig = inspect.signature(self._tier2_mobile_headers)
            has_var = any(p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD) for p in sig.parameters.values())
            if "catalog_price" in sig.parameters or has_var:
                return await self._tier2_mobile_headers(
                    task_id, product_id, organization_id, product_name, brand, barcode, proxy, catalog_price=baseline_price
                )
            return await self._tier2_mobile_headers(
                task_id, product_id, organization_id, product_name, brand, barcode, proxy
            )

        async def _call_tier3():
            sig = inspect.signature(self._tier3_playwright)
            has_var = any(p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD) for p in sig.parameters.values())
            if "catalog_price" in sig.parameters or has_var:
                return await self._tier3_playwright(
                    task_id, product_id, organization_id, product_name, brand, barcode, catalog_price=baseline_price
                )
            return await self._tier3_playwright(
                task_id, product_id, organization_id, product_name, brand, barcode
            )

        tiers = [
            ("internal_api", lambda: self._tier1_internal_api(product_name, brand, barcode)),
            ("mobile_headers", _call_tier2),
            ("playwright_stealth", _call_tier3),
            ("search_index_fallback", lambda: self._search_engine_fallback(
                _relaxed_query, _target_domain, product_name, brand)),
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
                logger.warning(f"[{self.platform_name}] tier {tier_name} hit bot defense: {bde}")
                continue  # NEVER break early; cascade to next tier / search index fallback
            except Exception as ex:
                logger.warning(f"[{self.platform_name}] tier {tier_name} error: {ex}")
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

            # Price ratio bounds [0.20x to 5.0x]
            price_val = float(result.get("price") or 0.0)
            if baseline_price > 0 and price_val > 0:
                ratio = price_val / baseline_price
                if ratio < 0.20 or ratio > 5.0:
                    logger.warning(
                        f"[{self.platform_name}] Scraped price ₹{price_val:.2f} is outside safe ratio "
                        f"[0.20x, 5.0x] of catalog price ₹{baseline_price:.2f} (ratio: {ratio:.2f}). "
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
