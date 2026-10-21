import asyncio
import hashlib
import json
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
    "lead", "leads", "case", "cover", "pouch",
    "bundle", "notebook", "eraser", "pencil",
    "protector", "tempered", "guard", "skin", "panel", "cable", "adapter", "strap",
    "display", "replacement", "touchscreen", "assembly"
}

NEGATIVE_ACCESSORY_PHRASES = (
    "tempered glass",
    "screen protector",
)


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

# Phase 8: Limit concurrent Playwright browser instances to prevent memory exhaustion
_playwright_semaphore: Optional[asyncio.Semaphore] = None


def _get_playwright_semaphore() -> asyncio.Semaphore:
    """Lazy-init semaphore using MAX_PLAYWRIGHT_BROWSERS from app config."""
    global _playwright_semaphore
    if _playwright_semaphore is None:
        try:
            from flask import current_app
            max_browsers = getattr(current_app.config, "MAX_PLAYWRIGHT_BROWSERS", 2) if current_app else 2
        except RuntimeError:
            max_browsers = 2
        _playwright_semaphore = asyncio.Semaphore(max_browsers)
    return _playwright_semaphore


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
        if status_code in (403, 471, 503):
            if any(term in lower_html for term in ["captcha", "challenge", "verify you are human", "robot", "datadome", "cloudflare", "perimeterx", "automated access", "request blocked"]):
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

        # Normalization: hyphens/plurals/apostrophes before token comparison
        # (levi's -> levis, t-shirt -> tshirt, earphones -> earphone, headphones -> headphone)
        def _normalize_title_text(text: str) -> str:
            text = text.replace("'", "")
            text = re.sub(r"\b(\w+)-(\w+)\b", r"\1\2", text)
            text = re.sub(r"\bt-shirt\b", "tshirt", text)
            text = re.sub(r"\bearphones\b", "earphone", text)
            text = re.sub(r"\bheadphones\b", "headphone", text)
            text = re.sub(r"(\d+)(mg|g|ml|kg|l|gb|tb|mb)\b", r"\1 \2", text)
            text = re.sub(r"\btablets\b", "tablet", text)
            text = re.sub(r"\bcapsules\b", "capsule", text)
            text = re.sub(r"\bshoes\b", "shoe", text)
            text = re.sub(r"\b(sheesham|acacia|teak|mango)\s+wood\b", "solid wood", text)
            return text

        title_norm = _normalize_title_text(title_norm)
        target_norm = _normalize_title_text(target_norm)
        brand_norm = _normalize_title_text(brand_norm)

        # Use strict regex whole-word boundaries so "Leading" != "lead" and "ThinkPad" != "ink"
        target_words = set(re.findall(r"\b[a-z0-9]+\b", target_norm))
        candidate_words = set(re.findall(r"\b[a-z0-9]+\b", title_norm))

        # Check multi-word negative accessory phrases (e.g. tempered glass, screen protector)
        for phrase in NEGATIVE_ACCESSORY_PHRASES:
            if phrase in title_norm and phrase not in target_norm:
                return 0.20

        # Check pack count: do not penalize "pack of 1" or "set of 1", but penalize multi-packs (e.g. pack of 2/3/4...)
        title_pack_match = re.search(r"\b(?:pack|set)\s+of\s+(\d+)\b", title_norm)
        if title_pack_match:
            pack_count = int(title_pack_match.group(1))
            if pack_count > 1 and not re.search(r"\b(?:pack|set)\s+of\s+" + str(pack_count) + r"\b", target_norm):
                return 0.20

        # Check single-word accessory tokens
        # Do NOT penalize "case", "cover", "pouch", "cable", "adapter" if preceded by "with", "includes", "including", or "and"
        included_acc_regex = re.compile(
            r"\b(?:with|includes|including|and)\s+(?:[\w-]+\s+){0,3}(?:case|cover|pouch|cable|adapter)\b",
            re.IGNORECASE
        )
        included_match = included_acc_regex.search(title_norm)
        included_text = included_match.group(0) if included_match else ""

        for token in NEGATIVE_ACCESSORY_TOKENS:
            if token in candidate_words and token not in target_words:
                if token in {"case", "cover", "pouch", "cable", "adapter"} and token in included_text:
                    continue  # Provided with the product (e.g. "with carrying case"), benign
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

        brand_matches = False
        if brand_norm:
            brand_tokens = [b for b in re.findall(r"\b[a-z0-9]+\b", brand_norm) if b not in stop_words]
            if brand_tokens and all(b in candidate_words or any(b in cw for cw in candidate_words) for b in brand_tokens):
                brand_matches = True
            elif brand_tokens:
                match_score *= 0.50

        # Model number tokens: alphanumeric with both letters and digits, length >= 3 (e.g. wh1000xm5, 1000xm5)
        model_number_tokens = {
            t for t in target_tokens
            if re.search(r"[a-z]", t) and re.search(r"\d", t) and len(t) >= 3
        }
        model_matches = bool(model_number_tokens) and any(
            any(mt == tt or (len(mt) >= 4 and (mt in tt or tt in mt)) for tt in title_tokens)
            for mt in model_number_tokens
        )
        token_match_ratio = len(intersection) / len(target_tokens) if target_tokens else 0.0

        # Boost match score by +0.12 (capped at 1.0) when brand matches AND (>=60% tokens match or exact model number matches)
        if brand_matches and (token_match_ratio >= 0.60 or model_matches):
            match_score = min(1.0, match_score + 0.12)

        # Price ratio bounds [0.20x to 5.0x]
        if catalog_price > 0 and scraped_price > 0:
            if scraped_price < (catalog_price * 0.20) or scraped_price > (catalog_price * 5.0):
                match_score = min(match_score, 0.40)

        return round(min(1.0, max(0.0, match_score)), 2)

    def _extract_structured_data(
        self,
        html_text: str,
        target_name: str,
        brand: str,
        barcode: str,
        fallback_url: str,
        catalog_price: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """
        Universal SSR Hydration & Metadata Extractor:
        1. JSON-LD scripts (<script type="application/ld+json">): Product, ItemList
        2. Next.js SSR Hydration (<script id="__NEXT_DATA__">)
        3. OpenGraph / Twitter / Schema meta tags
        Scores all discovered candidates using self.compute_match_score(...)
        and returns the highest-scoring candidate with score >= MATCH_THRESHOLD and price > 0.
        """
        if not html_text:
            return None

        candidates: List[Dict[str, Any]] = []

        def _parse_price(val: Any) -> float:
            if val is None:
                return 0.0
            if isinstance(val, (int, float)):
                return float(val) if val > 0 else 0.0
            if isinstance(val, str):
                cleaned = re.sub(r"[^\d\.]", "", val.replace(",", ""))
                try:
                    return float(cleaned) if cleaned else 0.0
                except (ValueError, TypeError):
                    return 0.0
            return 0.0

        from bs4 import BeautifulSoup
        try:
            soup = BeautifulSoup(html_text, "html.parser")
        except Exception:
            soup = None

        if soup:
            # 1. Parse all <script type="application/ld+json"> blocks
            ld_scripts = soup.find_all("script", type="application/ld+json")
            for script in ld_scripts:
                try:
                    content = script.string or script.text
                    if not content or not content.strip():
                        continue
                    data = json.loads(content)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        if "@graph" in item and isinstance(item["@graph"], list):
                            items.extend([g for g in item["@graph"] if isinstance(g, dict)])

                        item_type = str(item.get("@type", "")).lower()

                        if "product" in item_type:
                            name = item.get("name") or item.get("title")
                            offers = item.get("offers")
                            price = 0.0
                            mrp = None
                            in_stock = True
                            url = item.get("url")
                            if isinstance(offers, dict):
                                price = _parse_price(
                                    offers.get("price") or offers.get("lowPrice") or
                                    offers.get("priceSpecification", {}).get("price")
                                )
                                mrp_val = _parse_price(offers.get("highPrice"))
                                if mrp_val > price:
                                    mrp = mrp_val
                                avail = str(offers.get("availability", "")).lower()
                                if "outofstock" in avail or "discontinued" in avail:
                                    in_stock = False
                                if not url:
                                    url = offers.get("url")
                            elif isinstance(offers, list) and offers:
                                for off in offers:
                                    if isinstance(off, dict):
                                        p = _parse_price(off.get("price") or off.get("lowPrice"))
                                        if p > 0:
                                            price = p
                                            avail = str(off.get("availability", "")).lower()
                                            if "outofstock" in avail:
                                                in_stock = False
                                            if not url:
                                                url = off.get("url")
                                            break
                            if name and price > 0:
                                candidates.append({
                                    "title": str(name),
                                    "price": price,
                                    "mrp": mrp,
                                    "in_stock": in_stock,
                                    "url": str(url) if url else None,
                                    "source": "json_ld_product",
                                })

                        if "itemlist" in item_type:
                            elements = item.get("itemListElement") or []
                            if isinstance(elements, list):
                                for elem in elements:
                                    if not isinstance(elem, dict):
                                        continue
                                    target_obj = elem.get("item") if isinstance(elem.get("item"), dict) else elem
                                    name = target_obj.get("name") or target_obj.get("title")
                                    offers = target_obj.get("offers")
                                    price = 0.0
                                    url = target_obj.get("url")
                                    in_stock = True
                                    if isinstance(offers, dict):
                                        price = _parse_price(offers.get("price") or offers.get("lowPrice"))
                                        avail = str(offers.get("availability", "")).lower()
                                        if "outofstock" in avail:
                                            in_stock = False
                                    elif isinstance(offers, (int, float, str)):
                                        price = _parse_price(offers)
                                    if name and price > 0:
                                        candidates.append({
                                            "title": str(name),
                                            "price": price,
                                            "mrp": None,
                                            "in_stock": in_stock,
                                            "url": str(url) if url else None,
                                            "source": "json_ld_itemlist",
                                        })
                except Exception as ex:
                    logger.debug(f"[{self.platform_name}] json-ld parse error: {ex}")

            # 2. Parse <script id="__NEXT_DATA__" type="application/json">
            next_script = soup.find("script", id="__NEXT_DATA__")
            if next_script and (next_script.string or next_script.text):
                try:
                    next_json = json.loads(next_script.string or next_script.text)
                    def _find_products(obj, depth=0):
                        if depth > 10 or not obj:
                            return
                        if isinstance(obj, dict):
                            title_val = obj.get("name") or obj.get("title") or obj.get("productName")
                            price_val = (
                                obj.get("sellingPrice") or obj.get("price") or obj.get("final_price") or
                                obj.get("salePriceDecimal") or obj.get("min_catalog_price") or
                                obj.get("specialPrice")
                            )
                            if title_val and isinstance(title_val, str) and price_val is not None:
                                p = _parse_price(price_val)
                                if p > 0:
                                    mrp_val = _parse_price(
                                        obj.get("mrp") or obj.get("originalPrice") or obj.get("maximumRetailPrice")
                                    )
                                    url_val = (
                                        obj.get("pdpUrl") or obj.get("url") or
                                        obj.get("productUrl") or obj.get("slug")
                                    )
                                    is_avail = obj.get("inStock", obj.get("isAvailable", True))
                                    candidates.append({
                                        "title": title_val,
                                        "price": p,
                                        "mrp": mrp_val if mrp_val > p else None,
                                        "in_stock": bool(is_avail),
                                        "url": str(url_val) if url_val else None,
                                        "source": "next_data",
                                    })
                            for v in obj.values():
                                if isinstance(v, (dict, list)):
                                    _find_products(v, depth + 1)
                        elif isinstance(obj, list):
                            for elem in obj:
                                if isinstance(elem, (dict, list)):
                                    _find_products(elem, depth + 1)

                    _find_products(next_json)
                except Exception as ex:
                    logger.debug(f"[{self.platform_name}] __NEXT_DATA__ parse error: {ex}")

            # 3. Parse OpenGraph / meta tags
            og_title = (
                soup.find("meta", property="og:title")
                or soup.find("meta", attrs={"name": "twitter:title"})
            )
            og_price = (
                soup.find("meta", property="product:price:amount")
                or soup.find("meta", property="og:price:amount")
                or soup.find("meta", attrs={"itemprop": "price"})
            )
            og_url = (
                soup.find("meta", property="og:url")
                or soup.find("meta", attrs={"name": "twitter:url"})
            )
            og_avail = (
                soup.find("meta", property="product:availability")
                or soup.find("meta", attrs={"itemprop": "availability"})
            )
            if og_title and og_price:
                t_val = og_title.get("content", "").strip()
                p_val = _parse_price(og_price.get("content", ""))
                u_val = og_url.get("content", "").strip() if og_url else None
                av_val = og_avail.get("content", "").lower() if og_avail else ""
                in_stock_og = "outofstock" not in av_val
                if t_val and p_val > 0:
                    candidates.append({
                        "title": t_val,
                        "price": p_val,
                        "mrp": None,
                        "in_stock": in_stock_og,
                        "url": u_val,
                        "source": "meta_tags",
                    })

        if not candidates:
            return None

        # 4. Score all discovered candidates and return highest-scoring
        best_candidate = None
        best_score = -1.0

        for cand in candidates:
            score = self.compute_match_score(
                scraped_title=cand["title"],
                target_name=target_name,
                brand=brand,
                barcode=barcode,
                catalog_price=catalog_price,
                scraped_price=cand["price"],
            )
            if score >= MATCH_THRESHOLD and score > best_score:
                best_score = score
                best_candidate = cand

        if not best_candidate:
            return None

        cand_url = best_candidate.get("url") or fallback_url
        if cand_url.startswith("/"):
            cand_url = urljoin(self.base_url, cand_url)
        elif not cand_url.startswith("http"):
            cand_url = fallback_url

        try:
            validate_outbound_url(cand_url)
        except Exception:
            cand_url = fallback_url

        url_verified = (cand_url != fallback_url)

        return {
            "platform": self.platform_name,
            "price": best_candidate["price"],
            "mrp": best_candidate.get("mrp"),
            "currency": "INR",
            "in_stock": best_candidate.get("in_stock", True),
            "stock_status": "in_stock" if best_candidate.get("in_stock", True) else "out_of_stock",
            "product_url": cand_url,
            "url_verified": url_verified,
            "product_title": self.sanitize_output(best_candidate["title"]),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "match_score": best_score,
            "unverified_match": False,
            "scrape_mode": "structured_data",
            "data_source": "live_scrape",
        }

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
        from app.services.agentic.circuit_breaker import circuit_breaker
        return circuit_breaker._get_or_create(self.platform_name)

    def _circuit_allows_request(self) -> Tuple[bool, str]:
        """Returns (allowed, state_label)."""
        from app.services.agentic.circuit_breaker import circuit_breaker
        allowed, state, _ = circuit_breaker.allow(self.platform_name)
        return allowed, state

    def _record_scrape_success(self) -> None:
        from app.services.agentic.circuit_breaker import circuit_breaker
        circuit_breaker.record_success(self.platform_name)

    def _record_scrape_failure(self, reason: str, kind: Optional[Any] = None) -> None:
        from app.services.agentic.circuit_breaker import circuit_breaker, FailureKind
        if kind is None:
            r_lower = str(reason).lower()
            if "timeout" in r_lower:
                kind = FailureKind.TIMEOUT
            elif any(w in r_lower for w in ["blocked", "403", "429", "bot", "captcha", "challenge"]):
                kind = FailureKind.BLOCKED
            elif "validation" in r_lower or "parse" in r_lower:
                kind = FailureKind.PARSE_ERROR
            elif "no_match" in r_lower:
                kind = FailureKind.NO_MATCH
            else:
                kind = FailureKind.BLOCKED
        circuit_breaker.record_failure(self.platform_name, kind=kind, reason=reason)

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

        query = self.clean_search_query(product_name, brand)
        search_url = self.build_search_url(query)
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

        html_text = ""
        # 1. Attempt curl_cffi with chrome124 impersonation first
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(search_url, headers=mobile_headers, proxy=proxy, timeout=12)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200:
                    html_text = resp.text
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as ex:
            logger.debug(f"[{self.platform_name}] tier2 curl_cffi failed, falling back to aiohttp: {ex}")

        # 2. Fall back to aiohttp if curl_cffi didn't return HTML
        if not html_text:
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

        struct_res = self._extract_structured_data(html_text, product_name, brand, barcode, search_url, catalog_price)
        if struct_res:
            struct_res["scrape_mode"] = "mobile_headers"
            return struct_res

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
            "stock_status": "in_stock",
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
        # Phase 8: Acquire semaphore to limit concurrent browser instances
        sem = _get_playwright_semaphore()
        async with sem:
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

                captured_json_payloads: List[Tuple[str, Any]] = []

                async def _on_response(response):
                    try:
                        ct = response.headers.get("content-type", "")
                        if "application/json" in ct and response.status == 200:
                            url = response.url
                            data = await response.json()
                            if data:
                                captured_json_payloads.append((url, data))
                    except Exception:
                        pass

                page.on("response", _on_response)

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

            # 1. Custom card extraction
            card_res = self._invoke_extract_cards(html_text, product_name, brand, barcode, landed_url, catalog_price)
            if card_res:
                card_res["scrape_mode"] = "playwright_stealth"
                return card_res

            # 2. Universal structured data extraction (JSON-LD, __NEXT_DATA__, Meta)
            struct_res = self._extract_structured_data(html_text, product_name, brand, barcode, landed_url, catalog_price)
            if struct_res:
                struct_res["scrape_mode"] = "playwright_stealth"
                return struct_res

            # 3. Intercepted network JSON search
            if captured_json_payloads:
                best_cand = None
                best_s = -1.0
                for resp_url, data in captured_json_payloads:
                    candidates: List[Dict[str, Any]] = []

                    def _scan(obj, depth=0):
                        if depth > 8 or not obj:
                            return
                        if isinstance(obj, dict):
                            t_val = obj.get("name") or obj.get("title") or obj.get("productName")
                            p_val = (
                                obj.get("sellingPrice") or obj.get("price") or obj.get("final_price") or
                                obj.get("salePriceDecimal") or obj.get("min_catalog_price") or obj.get("specialPrice")
                            )
                            if t_val and p_val and isinstance(t_val, str):
                                try:
                                    p_clean = float(re.sub(r"[^\d\.]", "", str(p_val).replace(",", "")))
                                    if p_clean > 0:
                                        m_val = obj.get("mrp") or obj.get("originalPrice")
                                        m_clean = float(re.sub(r"[^\d\.]", "", str(m_val).replace(",", ""))) if m_val else None
                                        u_val = obj.get("pdpUrl") or obj.get("url") or obj.get("productUrl") or obj.get("slug")
                                        candidates.append({
                                            "title": str(t_val),
                                            "price": p_clean,
                                            "mrp": m_clean if m_clean and m_clean > p_clean else None,
                                            "url": str(u_val) if u_val else None,
                                            "in_stock": bool(obj.get("inStock", obj.get("isAvailable", True))),
                                        })
                                except Exception:
                                    pass
                            for v in obj.values():
                                if isinstance(v, (dict, list)):
                                    _scan(v, depth + 1)
                        elif isinstance(obj, list):
                            for el in obj:
                                if isinstance(el, (dict, list)):
                                    _scan(el, depth + 1)

                    _scan(data)
                    for c in candidates:
                        sc = self.compute_match_score(
                            c["title"], product_name, brand, barcode, catalog_price, c["price"]
                        )
                        if sc >= MATCH_THRESHOLD and sc > best_s:
                            best_s = sc
                            best_cand = c

                if best_cand:
                    c_url = best_cand.get("url") or landed_url
                    if c_url.startswith("/"):
                        c_url = urljoin(self.base_url, c_url)
                    elif not c_url.startswith("http"):
                        c_url = landed_url
                    try:
                        validate_outbound_url(c_url)
                    except Exception:
                        c_url = landed_url
                    return {
                        "platform": self.platform_name,
                        "price": best_cand["price"],
                        "mrp": best_cand.get("mrp"),
                        "currency": "INR",
                        "in_stock": best_cand.get("in_stock", True),
                        "stock_status": "in_stock" if best_cand.get("in_stock", True) else "out_of_stock",
                        "product_url": c_url,
                        "url_verified": c_url != landed_url,
                        "product_title": self.sanitize_output(best_cand["title"]),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": best_s,
                        "unverified_match": False,
                        "scrape_mode": "playwright_stealth",
                        "data_source": "live_scrape",
                    }

            # 4. Fallback DOM title & price parsing
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
                "stock_status": "in_stock",
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
        self, query: str, target_domain: str, product_name: str, brand: str, catalog_price: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """
        Multi-Engine Grounded Discovery:
        Extracts live marketplace prices and links via indexed search engine
        results (DuckDuckGo HTML, with Bing HTML fallback) when direct marketplace
        requests are blocked by WAFs.
        Grounded verification: validates canonical PDP links via fast 6-second
        curl_cffi probe (_extract_structured_data) or canonical path markers.
        """
        import aiohttp
        from bs4 import BeautifulSoup
        from urllib.parse import unquote

        clean_q = self.clean_search_query(product_name, brand)
        dork = quote_plus(f"site:{target_domain} {clean_q} price inr")
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://duckduckgo.com/",
        }

        async def _fetch_html(u: str) -> str:
            # 1. curl_cffi first
            try:
                from curl_cffi.requests import AsyncSession
                async with AsyncSession(impersonate="chrome124") as session:
                    resp = await session.get(u, headers=headers, timeout=8)
                    if resp.status_code == 200:
                        return resp.text
            except Exception:
                pass
            # 2. aiohttp fallback
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                    async with session.get(u, headers=headers) as resp:
                        if resp.status == 200:
                            return await resp.text()
            except Exception:
                pass
            return ""

        # Engine 1: DuckDuckGo HTML
        ddg_url = f"https://html.duckduckgo.com/html/?q={dork}"
        html_text = await _fetch_html(ddg_url)

        matched_offers: List[Tuple[float, float, str, str]] = []

        if html_text:
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
                                title or snippet, product_name, brand, catalog_price=catalog_price, scraped_price=price
                            )
                            if score >= MATCH_THRESHOLD:
                                final_url = clean_url if clean_url.startswith("http") else f"https://{clean_url.lstrip('/')}"
                                matched_offers.append((score, price, final_url, title))
            except Exception as e:
                logger.debug(f"[{self.platform_name}] duckduckgo parse error: {e}")

        # Engine 2: Bing HTML fallback if DDG returned no match or failed
        if not matched_offers:
            bing_url = f"https://www.bing.com/search?q={dork}"
            bing_html = await _fetch_html(bing_url)
            if bing_html:
                try:
                    soup = BeautifulSoup(bing_html, "html.parser")
                    for result in soup.select("li.b_algo"):
                        link_node = result.select_one("h2 a")
                        href = link_node.get("href", "") if link_node else ""
                        clean_url = href
                        m_u = re.search(r"[?&]u=a1([^&]+)", href)
                        if m_u:
                            raw_b64 = m_u.group(1)
                            pad = len(raw_b64) % 4
                            if pad:
                                raw_b64 += "=" * (4 - pad)
                            try:
                                import base64
                                clean_url = base64.b64decode(raw_b64).decode("utf-8", errors="ignore")
                            except Exception:
                                pass

                        if not clean_url or target_domain not in clean_url or "bing.com/aclick" in clean_url:
                            continue

                        snippet_node = result.select_one(".b_caption p, .b_snippet")
                        snippet = snippet_node.get_text(strip=True) if snippet_node else ""
                        title_node = result.select_one("h2")
                        title = title_node.get_text(strip=True) if title_node else ""

                        price_match = re.search(
                            r"(?:\u20b9|Rs\.?|INR)\s*([\d,]+(?:\.\d{2})?)", snippet + " " + title
                        )
                        if price_match:
                            price = float(price_match.group(1).replace(",", ""))
                            if price > 0:
                                score = self.compute_match_score(
                                    title or snippet, product_name, brand, catalog_price=catalog_price, scraped_price=price
                                )
                                if score >= MATCH_THRESHOLD:
                                    final_url = clean_url if clean_url.startswith("http") else f"https://{clean_url.lstrip('/')}"
                                    matched_offers.append((score, price, final_url, title))
                except Exception as e:
                    logger.debug(f"[{self.platform_name}] bing parse error: {e}")

        # Engine 3: Yahoo Search HTML fallback if DDG and Bing returned no match
        if not matched_offers:
            yahoo_url = f"https://search.yahoo.com/search?p={dork}"
            yahoo_html = await _fetch_html(yahoo_url)
            if yahoo_html:
                try:
                    soup = BeautifulSoup(yahoo_html, "html.parser")
                    for result in soup.select(".algo, .dd.algo"):
                        link_node = result.find("a", href=True)
                        href = link_node.get("href", "") if link_node else ""
                        clean_url = href
                        m_y = re.search(r"/RU=([^/]+)/", href)
                        if m_y:
                            clean_url = unquote(m_y.group(1))
                        if not clean_url or target_domain not in clean_url:
                            continue

                        title_node = result.find(["h3", "h4"])
                        title = title_node.get_text(strip=True) if title_node else ""
                        snippet_node = result.select_one(".compText, .b_caption")
                        snippet = snippet_node.get_text(strip=True) if snippet_node else ""

                        price_match = re.search(
                            r"(?:\u20b9|Rs\.?|INR)\s*([\d,]+(?:\.\d{2})?)", snippet + " " + title
                        )
                        if price_match:
                            price = float(price_match.group(1).replace(",", ""))
                            if price > 0:
                                score = self.compute_match_score(
                                    title or snippet, product_name, brand, catalog_price=catalog_price, scraped_price=price
                                )
                                if score >= MATCH_THRESHOLD:
                                    final_url = clean_url if clean_url.startswith("http") else f"https://{clean_url.lstrip('/')}"
                                    matched_offers.append((score, price, final_url, title))
                except Exception as e:
                    logger.debug(f"[{self.platform_name}] yahoo parse error: {e}")

        if not matched_offers:
            return None

        # Sort by match score descending
        matched_offers.sort(key=lambda x: x[0], reverse=True)
        best_score, best_price, best_url, best_title = matched_offers[0]

        # Grounded PDP probe: attempt fast 6-second curl_cffi GET on canonical PDP
        pdp_html = ""
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome124") as session:
                pdp_resp = await session.get(best_url, headers=headers, timeout=6)
                if pdp_resp.status_code == 200:
                    pdp_html = pdp_resp.text
        except Exception:
            pass

        if pdp_html:
            live_offer = self._extract_structured_data(
                pdp_html, product_name, brand, "", best_url, catalog_price=catalog_price
            )
            if live_offer:
                live_offer["data_source"] = "live_scrape"
                live_offer["scrape_mode"] = "search_verified_pdp"
                return live_offer

        # If direct probe blocked or structured data not present, check canonical product path markers
        is_canonical_pdp = any(marker in best_url for marker in _PRODUCT_PATH_MARKERS)
        data_source = "live_scrape" if is_canonical_pdp else "search_index_snippet"
        scrape_mode = "search_verified_pdp" if is_canonical_pdp else "search_index_fallback"

        return {
            "platform": self.platform_name,
            "price": best_price,
            "mrp": None,
            "currency": "INR",
            "in_stock": True,
            "stock_status": "in_stock",
            "product_url": best_url,
            "url_verified": True,
            "product_title": self.sanitize_output(best_title or f"Verified {self.platform_name} listing"),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "match_score": best_score,
            "unverified_match": False,
            "scrape_mode": scrape_mode,
            "data_source": data_source,
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
                "failure_kind": "circuit_open",
                "latency_ms": 1.0,
            }

        proxy = self.proxy_manager.get_proxy()
        _target_domain = self.base_url.replace("https://", "").replace("http://", "").rstrip("/")
        _relaxed_query = self.clean_search_query(product_name, brand)

        import inspect

        async def _call_tier1():
            sig = inspect.signature(self._tier1_internal_api)
            has_var = any(p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD) for p in sig.parameters.values())
            if "catalog_price" in sig.parameters or has_var:
                return await self._tier1_internal_api(product_name, brand, barcode, catalog_price=baseline_price)
            return await self._tier1_internal_api(product_name, brand, barcode)

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
            ("internal_api", _call_tier1),
            ("mobile_headers", _call_tier2),
            ("playwright_stealth", _call_tier3),
            ("search_index_fallback", lambda: self._search_engine_fallback(
                _relaxed_query, _target_domain, product_name, brand, catalog_price=baseline_price)),
        ]

        from app.services.agentic.circuit_breaker import FailureKind
        last_reason = "no_tier_produced_a_verified_match"
        last_kind = FailureKind.NO_MATCH

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
                last_kind = FailureKind.BLOCKED
                logger.warning(f"[{self.platform_name}] tier {tier_name} hit bot defense: {bde}")
                continue  # NEVER break early; cascade to next tier / search index fallback
            except asyncio.TimeoutError as te:
                last_reason = f"{tier_name}_timeout: {te}"
                last_kind = FailureKind.TIMEOUT
                logger.warning(f"[{self.platform_name}] tier {tier_name} timed out: {te}")
                continue
            except Exception as ex:
                if "timeout" in str(ex).lower():
                    last_kind = FailureKind.TIMEOUT
                else:
                    last_kind = FailureKind.PARSE_ERROR
                logger.warning(f"[{self.platform_name}] tier {tier_name} error: {ex}")
                last_reason = f"{tier_name}_exception: {ex}"
                continue

            if raw_result is None:
                last_reason = f"{tier_name}_no_match"
                last_kind = FailureKind.NO_MATCH
                continue

            try:
                validated = ScrapedOffer(**raw_result)
            except ValidationError as ve:
                logger.warning(f"[{self.platform_name}] tier {tier_name} produced invalid offer: {ve}")
                last_reason = f"{tier_name}_validation_failed: {ve}"
                last_kind = FailureKind.PARSE_ERROR
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
                    last_kind = FailureKind.NO_MATCH
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
        self._record_scrape_failure(last_reason, kind=last_kind)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
        failure_kind_val = getattr(last_kind, "value", str(last_kind))
        await self.emit_event(
            task_id=task_id, product_id=product_id, organization_id=organization_id,
            event_type="scraper_failed",
            message=f"{self.platform_name} failed across all tiers: {last_reason}",
            payload={"platform": self.platform_name, "error": last_reason, "failure_kind": failure_kind_val},
        )
        return {
            "platform": self.platform_name, "status": "unreachable",
            "reason": last_reason, "match_score": 0.0,
            "unverified_match": True, "data_source": "estimated_fallback",
            "failure_kind": failure_kind_val,
            "latency_ms": latency_ms,
        }
