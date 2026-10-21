import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from app.services.agentic.scrapers.base_scraper import (
    BaseScraperAgent,
    BotDetectionEncountered,
    MATCH_THRESHOLD,
    PlatformRateLimitError,
    _get_playwright_semaphore,
)
from app.utils.security_guardrails import validate_outbound_url

logger = logging.getLogger(__name__)


class AmazonScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Amazon.in",
            search_url_template="https://www.amazon.in/s?k={query}",
            base_url="https://www.amazon.in",
        )

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str) -> Optional[Dict[str, Any]]:
        query = self.clean_search_query(product_name, brand)
        search_url = self.build_search_url(query)
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
        }
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(search_url, headers=headers, timeout=12)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200:
                    candidate = self._extract_amazon_cards(resp.text, product_name, brand, barcode, search_url)
                    if candidate:
                        candidate["scrape_mode"] = "internal_api"
                        return candidate

                    # Retry once with first 3 core tokens if query is long (> 3 tokens)
                    tokens = query.split()
                    if len(tokens) > 3:
                        relaxed_query = " ".join(tokens[:3])
                        relaxed_url = self.build_search_url(relaxed_query)
                        resp_retry = await session.get(relaxed_url, headers=headers, timeout=12)
                        self.check_bot_detection(resp_retry.status_code, resp_retry.text)
                        if resp_retry.status_code == 200:
                            cand_retry = self._extract_amazon_cards(resp_retry.text, product_name, brand, barcode, relaxed_url)
                            if cand_retry:
                                cand_retry["scrape_mode"] = "internal_api"
                                return cand_retry
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            logger.warning(f"[{self.platform_name}] tier1 anti-bot / rate-limit encountered: {bde}")
            raise bde
        except Exception as ex:
            logger.debug(f"[{self.platform_name}] tier1 internal_api error: {ex}")
        return None

    def _extract_amazon_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_rank = -1.0

            # Target only organic search result cards (exclude sponsored ads)
            items = soup.select('div[data-component-type="s-search-result"]:not(.AdHolder)')
            target_lower = target_name.lower()
            is_refill_target = "refill" in target_lower

            for item in items:
                # Exclude sponsored badge or ad markers
                if item.select_one(".puis-sponsored-label-text, .s-sponsored-label-text, .AdHolder"):
                    continue

                title_node = item.find("h2")
                recipe_node = item.select_one('[data-cy="title-recipe"], .s-title-instructions-style')
                headers = [
                    h.get_text(separator=' ', strip=True)
                    for h in (recipe_node.find_all(["h2", "h3"]) if recipe_node else item.find_all(["h2", "h3"]))
                    if h.get_text(strip=True)
                ]
                if len(headers) >= 2 and len(headers[0]) < 25:
                    title = " ".join(headers)
                elif recipe_node and recipe_node.select_one("a.a-link-normal.s-line-clamp-2, a.a-link-normal.s-line-clamp-4"):
                    title = recipe_node.select_one("a.a-link-normal.s-line-clamp-2, a.a-link-normal.s-line-clamp-4").get_text(separator=' ', strip=True)
                elif headers:
                    title = headers[0]
                else:
                    if not title_node:
                        continue
                    title = title_node.get_text(separator=' ', strip=True)
                title_lower = title.lower()

                # Exclude refills if catalog query is a single unit pen
                if "refill" in title_lower and not is_refill_target:
                    continue

                # Strict Price Selector Scoping:
                # 1. .s-price-instructions-style .a-price:not(.a-text-price) .a-offscreen
                # 2. .a-price:not(.a-text-price) .a-offscreen
                # 3. .s-price-instructions-style .a-price .a-offscreen
                # 4. .a-price-whole fallback
                price_container = (
                    item.select_one(".s-price-instructions-style .a-price:not(.a-text-price) .a-offscreen")
                    or item.select_one(".a-price:not(.a-text-price) .a-offscreen")
                    or item.select_one(".s-price-instructions-style .a-price .a-offscreen")
                    or item.select_one(".a-price .a-offscreen")
                )
                price = 0.0
                if price_container:
                    p_text = price_container.get_text(strip=True)
                    clean_p = re.sub(r"[^\d.]", "", p_text.replace(",", ""))
                    try:
                        price = float(clean_p)
                    except ValueError:
                        price = 0.0

                if price <= 0:
                    whole_node = item.select_one(".s-price-instructions-style .a-price-whole") or item.select_one(".a-price-whole")
                    if whole_node:
                        clean_whole = re.sub(r"[^\d.]", "", whole_node.get_text(strip=True).replace(",", ""))
                        try:
                            price = float(clean_whole)
                        except ValueError:
                            price = 0.0

                if price <= 0:
                    continue

                score = self.compute_match_score(
                    title, target_name, brand, barcode,
                    catalog_price=catalog_price, scraped_price=price
                )
                if score < MATCH_THRESHOLD:
                    continue

                # MRP / list price inside price instructions
                mrp = None
                mrp_container = (
                    item.select_one(".s-price-instructions-style .a-price.a-text-price .a-offscreen")
                    or item.select_one(".a-text-price .a-offscreen")
                )
                if mrp_container:
                    clean_m = re.sub(r"[^\d.]", "", mrp_container.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                # Live Product URL:
                # 1. item.get("data-asin") -> https://www.amazon.in/dp/{asin}
                # 2. a.a-link-normal[href*="/dp/"]
                # 3. Fallback to standard product link selectors
                prod_url = search_url
                url_verified = False

                asin = item.get("data-asin", "").strip()
                if asin and re.match(r"^[A-Z0-9]{10}$", asin):
                    prod_url = f"https://www.amazon.in/dp/{asin}"
                    url_verified = True
                else:
                    link_node = (
                        item.select_one('a.a-link-normal[href*="/dp/"]')
                        or item.select_one("a.a-link-normal.s-no-outline[href]")
                        or (title_node.find("a", href=True) if title_node else None)
                        or item.select_one("a.a-link-normal.s-underline-text[href]")
                        or item.select_one("a.a-link-normal[href]")
                    )
                    if link_node and link_node.get("href"):
                        raw_href = link_node["href"]
                        asin_match = re.search(r"(/dp/[A-Z0-9]{10})", raw_href)
                        if asin_match:
                            prod_url = f"https://www.amazon.in{asin_match.group(1)}"
                            url_verified = True
                        elif raw_href.startswith("http"):
                            prod_url = raw_href
                            url_verified = True
                        elif raw_href.startswith("/"):
                            prod_url = f"https://www.amazon.in{raw_href.split('?')[0]}"
                            url_verified = True

                # Rank by score and proximity to catalog_price if catalog_price > 0
                if catalog_price > 0:
                    diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                    rank = score - (0.25 * diff_ratio)
                else:
                    rank = score

                if rank > best_rank:
                    best_rank = rank
                    best_candidate = {
                        "platform": "Amazon.in",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }

            return best_candidate
        except Exception as e:
            logger.warning(f"[AmazonScraperAgent] parsing error: {e}", exc_info=True)
            return None

    _extract_cards = _extract_amazon_cards

    async def _tier2_mobile_headers(
        self, task_id: str, product_id: str, organization_id: str,
        product_name: str, brand: str, barcode: str, proxy: Optional[str] = None,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        import aiohttp
        query = product_name.strip()
        if brand and brand.lower() not in product_name.lower():
            query = f"{brand} {product_name}".strip()
        search_url = self.build_search_url(query)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
                async with session.get(search_url, headers=headers, proxy=proxy) as resp:
                    html_text = await resp.text()
                    self.check_bot_detection(resp.status, html_text)
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            logger.info(f"[Amazon.in] tier2 HTTP bot challenge encountered; delegating to Playwright: {bde}")
            return None
        except Exception as ex:
            logger.warning(f"[Amazon.in] HTTP request error: {ex}")
            return None

        return self._extract_amazon_cards(html_text, product_name, brand, barcode, search_url, catalog_price=catalog_price)

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

        # Use relaxed query for better match rates
        query = self.clean_search_query(product_name, brand)
        search_url = self.build_search_url(query)
        try:
            validate_outbound_url(search_url)
        except ValueError as ex:
            logger.warning(f"[{self.platform_name}] tier3 refused unsafe URL: {ex}")
            return None

        # Concurrency safety: acquire Playwright semaphore
        sem = _get_playwright_semaphore()
        html_text = ""
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
                    locale="en-IN",
                    viewport={"width": 1366, "height": 768},
                    timezone_id="Asia/Kolkata",
                )

                # Stealth evasions to bypass Amazon CAPTCHA fingerprinting
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

                # Block heavy assets to speed up execution
                await page.route(
                    re.compile(r"\.(png|jpg|jpeg|gif|webp|svg|ico|woff|woff2)(\?.*)?$"),
                    lambda r: r.abort()
                )

                await page.goto(search_url, timeout=25000, wait_until="domcontentloaded")

                # Wait for search result cards before extracting HTML (timeout 8000ms)
                try:
                    await page.wait_for_selector('div[data-component-type="s-search-result"]', timeout=8000)
                except Exception:
                    await page.wait_for_timeout(2000)

                html_text = await page.content()
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

        if not html_text:
            return None

        candidate = self._extract_amazon_cards(html_text, product_name, brand, barcode, search_url, catalog_price=catalog_price)
        if candidate:
            candidate["scrape_mode"] = "playwright_stealth"
            return candidate

        return None


class FlipkartScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Flipkart",
            search_url_template="https://www.flipkart.com/search?q={query}",
            base_url="https://www.flipkart.com",
        )

    def _extract_from_initial_state(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        pos = html_text.find("window.__INITIAL_STATE__")
        if pos == -1:
            return None
        start = html_text.find("{", pos)
        if start == -1:
            return None
        try:
            state, _ = json.JSONDecoder().raw_decode(html_text[start:])
            page_data = state.get("pageDataV4", {}).get("page", {}).get("data", {})
            if not isinstance(page_data, dict):
                return None

            best_candidate = None
            best_rank = -1.0

            for slot_key, slot_val in page_data.items():
                if not isinstance(slot_val, list):
                    continue
                for item in slot_val:
                    if not isinstance(item, dict):
                        continue
                    widget = item.get("widget", {})
                    if not isinstance(widget, dict):
                        continue
                    w_data = widget.get("data", {})
                    if not isinstance(w_data, dict):
                        continue

                    raw_products = []
                    if isinstance(w_data.get("products"), list):
                        raw_products.extend(w_data["products"])
                    if isinstance(w_data.get("productSummary"), dict):
                        raw_products.append({"productInfo": {"value": w_data["productSummary"]}})

                    for prod in raw_products:
                        if not isinstance(prod, dict):
                            continue
                        p_info = prod.get("productInfo", {}).get("value", {})
                        if not isinstance(p_info, dict):
                            p_info = prod.get("productSummary") or prod

                        titles = p_info.get("titles", {})
                        if isinstance(titles, dict):
                            title = titles.get("newTitle") or titles.get("title") or titles.get("superTitle", "")
                        else:
                            title = p_info.get("title") or ""
                        if not title:
                            continue

                        title = re.sub(r"(?i)\badd to compare\b|\bcurrently unavailable\b", "", str(title)).strip()

                        pricing = p_info.get("pricing", {})
                        price = 0.0
                        mrp = None
                        if isinstance(pricing, dict):
                            if "finalPrice" in pricing and isinstance(pricing["finalPrice"], dict):
                                try:
                                    price = float(pricing["finalPrice"].get("value", 0))
                                except (ValueError, TypeError):
                                    price = 0.0
                            elif "prices" in pricing and isinstance(pricing["prices"], list):
                                for p_entry in pricing["prices"]:
                                    if isinstance(p_entry, dict):
                                        if p_entry.get("strikeOff") is False:
                                            try:
                                                price = float(p_entry.get("value", 0))
                                            except (ValueError, TypeError):
                                                pass
                                        elif p_entry.get("strikeOff") is True:
                                            try:
                                                mrp = float(p_entry.get("value", 0))
                                            except (ValueError, TypeError):
                                                pass
                            if "mrp" in pricing and isinstance(pricing["mrp"], dict):
                                try:
                                    mrp = float(pricing["mrp"].get("value", 0))
                                except (ValueError, TypeError):
                                    pass

                        if price <= 0:
                            continue

                        score = self.compute_match_score(
                            title, target_name, brand, barcode,
                            catalog_price=catalog_price, scraped_price=price
                        )
                        if score < MATCH_THRESHOLD:
                            continue

                        raw_url = p_info.get("baseUrl") or prod.get("action", {}).get("url")
                        prod_url = search_url
                        url_verified = False
                        if raw_url:
                            clean_href = str(raw_url).split("?")[0]
                            if clean_href.startswith("/"):
                                prod_url = f"https://www.flipkart.com{clean_href}"
                                url_verified = True
                            elif clean_href.startswith("http"):
                                prod_url = clean_href
                                url_verified = True

                        if catalog_price > 0:
                            diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                            rank = score - (0.25 * diff_ratio)
                        else:
                            rank = score

                        if rank > best_rank:
                            best_rank = rank
                            best_candidate = {
                                "platform": "Flipkart",
                                "price": price,
                                "mrp": mrp if (mrp and mrp >= price) else None,
                                "currency": "INR",
                                "in_stock": True,
                                "stock_status": "in_stock",
                                "product_url": prod_url,
                                "url_verified": url_verified,
                                "product_title": self.sanitize_output(title),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "match_score": score,
                                "unverified_match": False,
                                "scrape_mode": "internal_api",
                                "data_source": "live_scrape",
                            }

            return best_candidate
        except Exception as e:
            logger.debug(f"[Flipkart] __INITIAL_STATE__ parse error: {e}")
            return None

    def _extract_flipkart_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_rank = -1.0

            # Target all modern Flipkart container layouts
            cards = soup.select("div[data-id], div.tUxRFH, div.slAVV4, div._4ddWXP, div.cPHDOP")

            for card in cards:
                title_node = (
                    card.select_one(
                        "div.KzDlHZ, div._4rR01T, a.wjcEIp, a.s1Q9rs, a.VJA3rP, a.pIpigb, a[title]"
                    )
                    or card.select_one("img[alt]")
                    or card.find("a", href=True)
                )
                if not title_node:
                    continue
                if title_node.name == "img" and title_node.get("alt"):
                    title = title_node["alt"].strip()
                else:
                    title = title_node.get_text(separator=" ", strip=True) or title_node.get("title") or ""
                title = re.sub(r"(?i)\badd to compare\b|\bcurrently unavailable\b", "", title).strip()

                # Flexible price extraction
                price_node = card.select_one("div.Nx9bqj, div._30jeq3, div.hZ3P6w")
                if not price_node:
                    match = re.search(
                        r"(?:₹|Rs\.?)\s*([\d,]+(?:\.\d{2})?)",
                        card.get_text(strip=True),
                    )
                    if match:
                        clean_p = match.group(1).replace(",", "")
                    else:
                        continue
                else:
                    clean_p = re.sub(
                        r"[^\d.]", "",
                        price_node.get_text(strip=True).replace(",", ""),
                    )
                try:
                    price = float(clean_p)
                except ValueError:
                    continue
                if price <= 0:
                    continue

                score = self.compute_match_score(
                    title, target_name, brand, barcode,
                    catalog_price=catalog_price, scraped_price=price
                )
                if score < MATCH_THRESHOLD:
                    continue

                # MRP
                mrp = None
                mrp_node = card.select_one("div.yRaY8j, div.kRYCnD, div._3I9_wc")
                if mrp_node:
                    clean_m = re.sub(
                        r"[^\d.]", "",
                        mrp_node.get_text(strip=True).replace(",", ""),
                    )
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                # Canonical Link
                link_node = (
                    card.select_one("a[href*='/p/']")
                    or card.select_one(
                        "a.CGtC98[href], a._1fQZEK[href], a.wjcEIp[href], "
                        "a.s1Q9rs[href], a.VJA3rP[href], a.pIpigb[href]"
                    )
                    or card.find("a", href=True)
                )
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"]
                    clean_href = href.split("?")[0]
                    if clean_href.startswith("/"):
                        prod_url = f"https://www.flipkart.com{clean_href}"
                        url_verified = True
                    elif clean_href.startswith("http"):
                        prod_url = clean_href
                        url_verified = True

                if catalog_price > 0:
                    diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                    rank = score - (0.25 * diff_ratio)
                else:
                    rank = score

                if rank > best_rank:
                    best_rank = rank
                    best_candidate = {
                        "platform": "Flipkart",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }

            return best_candidate
        except Exception as e:
            logger.debug(f"[FlipkartScraperAgent] parsing error: {e}")
            return None

    _extract_cards = _extract_flipkart_cards

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str) -> Optional[Dict[str, Any]]:
        """Tier 1: Desktop Chrome 124 TLS search extracting __INITIAL_STATE__ or DOM cards."""
        query = self.clean_search_query(product_name, brand)
        search_url = self.build_search_url(query)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
        }
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(search_url, headers=headers, timeout=12)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200:
                    cand = self._extract_from_initial_state(
                        resp.text, product_name, brand, barcode, search_url
                    )
                    if cand:
                        cand["scrape_mode"] = "internal_api"
                        return cand

                    cand_dom = self._extract_flipkart_cards(
                        resp.text, product_name, brand, barcode, search_url
                    )
                    if cand_dom:
                        cand_dom["scrape_mode"] = "internal_api"
                        return cand_dom
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            logger.warning(f"[{self.platform_name}] tier1 anti-bot encountered: {bde}")
            raise bde
        except Exception as e:
            logger.debug(f"[{self.platform_name}] tier1 internal_api error: {e}")
        return None

    async def _tier2_mobile_headers(
        self, task_id: str, product_id: str, organization_id: str,
        product_name: str, brand: str, barcode: str, proxy: Optional[str] = None,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        import aiohttp
        search_url = self.build_search_url(f"{brand} {product_name}".strip())
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as session:
                async with session.get(search_url, headers=headers, proxy=proxy) as resp:
                    html_text = await resp.text()
                    self.check_bot_detection(resp.status, html_text)
                    candidate = self._extract_flipkart_cards(html_text, product_name, brand, barcode, search_url, catalog_price=catalog_price)
                    if candidate:
                        return candidate
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            logger.info(f"[Flipkart] tier2 HTTP bot challenge; falling back to Playwright: {bde}")
            return None
        except Exception as ex:
            logger.warning(f"[Flipkart] HTTP request error: {ex}")
            return None

        return None

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

        # Use relaxed query for better marketplace match rates
        query = self.clean_search_query(product_name, brand)
        search_url = self.build_search_url(query)
        try:
            validate_outbound_url(search_url)
        except ValueError as ex:
            logger.warning(f"[{self.platform_name}] tier3 refused unsafe URL: {ex}")
            return None

        # Concurrency safety: acquire Playwright semaphore
        sem = _get_playwright_semaphore()
        html_text = ""
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
                    locale="en-IN",
                    viewport={"width": 1366, "height": 768},
                    timezone_id="Asia/Kolkata",
                )

                # Stealth evasions to bypass Flipkart's anti-bot fingerprinting
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

                # Block heavy images for rapid execution
                await page.route(
                    re.compile(r"\.(png|jpg|jpeg|gif|webp|ico)(\?.*)?$"),
                    lambda r: r.abort(),
                )
                await page.goto(search_url, timeout=25000, wait_until="domcontentloaded")

                # Dismiss Flipkart login modal
                try:
                    await page.keyboard.press("Escape")
                    close_btn = page.locator(
                        "button._2KpZ6l._2doB4z, span._30XB9F, button:has-text('✕')"
                    ).first
                    if await close_btn.is_visible(timeout=1500):
                        await close_btn.click()
                except Exception:
                    pass

                # Wait for any of the known container classes to appear
                try:
                    await page.locator(
                        "div[data-id], div.tUxRFH, div.slAVV4, div._4ddWXP, div.cPHDOP"
                    ).first.wait_for(timeout=6000)
                except Exception:
                    pass

                # Give dynamic cards time to render
                await page.wait_for_timeout(2500)

                html_text = await page.content()
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

        if not html_text:
            return None

        candidate = self._extract_flipkart_cards(html_text, product_name, brand, barcode, search_url, catalog_price=catalog_price)
        if candidate:
            candidate["scrape_mode"] = "playwright_stealth"
            return candidate

        return None


class MyntraScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Myntra",
            search_url_template="https://www.myntra.com/{query}",
            base_url="https://www.myntra.com",
        )

    async def _tier1_internal_api(
        self, product_name: str, brand: str, barcode: str, catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Tier 1: Desktop Chrome 124 TLS fetch of Myntra slug with window.__myx JSON and Gateway v2 fallback."""
        import json
        from urllib.parse import quote_plus
        from curl_cffi.requests import AsyncSession

        clean_query = self.clean_search_query(product_name, brand)
        if brand and brand.lower() in clean_query.lower():
            words = clean_query.split()
            deduped = []
            for w in words:
                if not deduped or w.lower() != brand.lower() or deduped[-1].lower() != brand.lower():
                    deduped.append(w)
            clean_query = " ".join(deduped)

        slug = re.sub(r"[^a-z0-9]+", "-", clean_query.lower()).strip("-")
        search_url = f"https://www.myntra.com/{slug}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
        }

        try:
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(search_url, headers=headers, timeout=12)
                self.check_bot_detection(resp.status_code, resp.text)
                best_candidate = None
                best_rank = -1.0

                if resp.status_code == 200:
                    idx = resp.text.find("window.__myx = ")
                    if idx != -1:
                        raw = resp.text[idx + len("window.__myx = "):]
                        end = raw.find("</script>")
                        clean_json = raw[:end].strip().rstrip(";")
                        try:
                            data = json.loads(clean_json)
                            products = data.get("searchData", {}).get("results", {}).get("products", [])
                            for p in products:
                                full_title = f"{p.get('brand', '')} {p.get('productName', '')}".strip()
                                if not full_title:
                                    full_title = p.get("product") or ""
                                try:
                                    price = float(p.get("price", 0))
                                except (ValueError, TypeError):
                                    continue
                                if price <= 0:
                                    continue
                                try:
                                    mrp = float(p.get("mrp", 0))
                                except (ValueError, TypeError):
                                    mrp = 0.0

                                score = self.compute_match_score(
                                    full_title, product_name, brand, barcode,
                                    catalog_price=catalog_price, scraped_price=price
                                )
                                if score < MATCH_THRESHOLD:
                                    continue

                                landing_url = p.get("landingPageUrl") or ""
                                prod_url = f"https://www.myntra.com/{landing_url.lstrip('/')}" if landing_url else search_url
                                url_verified = bool(landing_url)

                                if catalog_price > 0:
                                    diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                                    rank = score - (0.25 * diff_ratio)
                                else:
                                    rank = score

                                if rank > best_rank:
                                    best_rank = rank
                                    best_candidate = {
                                        "platform": "Myntra",
                                        "price": price,
                                        "mrp": mrp if mrp >= price else None,
                                        "currency": "INR",
                                        "in_stock": True,
                                        "stock_status": "in_stock",
                                        "product_url": prod_url,
                                        "url_verified": url_verified,
                                        "product_title": self.sanitize_output(full_title),
                                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                                        "match_score": score,
                                        "unverified_match": False,
                                        "scrape_mode": "internal_api",
                                        "data_source": "live_scrape",
                                    }
                        except Exception as jex:
                            logger.debug(f"[Myntra] window.__myx JSON parse error: {jex}")

                if best_candidate:
                    return best_candidate

                # 2. Gateway API search fallback in the same session
                gw_url = f"https://www.myntra.com/gateway/v2/search/{quote_plus(clean_query)}?rows=20&o=0"
                gw_headers = {
                    "User-Agent": headers["User-Agent"],
                    "Accept": "application/json",
                    "Referer": search_url,
                }
                try:
                    gw_resp = await session.get(gw_url, headers=gw_headers, timeout=10)
                    if gw_resp.status_code == 200:
                        gw_data = gw_resp.json()
                        gw_products = gw_data.get("products", [])
                        for p in gw_products:
                            full_title = f"{p.get('brand', '')} {p.get('productName', '')}".strip()
                            if not full_title:
                                full_title = p.get("product") or ""
                            try:
                                price = float(p.get("price", 0))
                            except (ValueError, TypeError):
                                continue
                            if price <= 0:
                                continue
                            try:
                                mrp = float(p.get("mrp", 0))
                            except (ValueError, TypeError):
                                mrp = 0.0

                            score = self.compute_match_score(
                                full_title, product_name, brand, barcode,
                                catalog_price=catalog_price, scraped_price=price
                            )
                            if score < MATCH_THRESHOLD:
                                continue

                            landing_url = p.get("landingPageUrl") or ""
                            prod_url = f"https://www.myntra.com/{landing_url.lstrip('/')}" if landing_url else search_url
                            url_verified = bool(landing_url)

                            if catalog_price > 0:
                                diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                                rank = score - (0.25 * diff_ratio)
                            else:
                                rank = score

                            if rank > best_rank:
                                best_rank = rank
                                best_candidate = {
                                    "platform": "Myntra",
                                    "price": price,
                                    "mrp": mrp if mrp >= price else None,
                                    "currency": "INR",
                                    "in_stock": True,
                                    "stock_status": "in_stock",
                                    "product_url": prod_url,
                                    "url_verified": url_verified,
                                    "product_title": self.sanitize_output(full_title),
                                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                                    "match_score": score,
                                    "unverified_match": False,
                                    "scrape_mode": "internal_api",
                                    "data_source": "live_scrape",
                                }
                except Exception as gw_ex:
                    logger.debug(f"[Myntra] Gateway v2 search error: {gw_ex}")

                return best_candidate
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.warning(f"[Myntra] Tier 1 extraction failed: {e}")

        return None

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from Myntra search result HTML."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_rank = -1.0

            cards = (
                soup.select("li.product-base")
                or soup.select("div.product-base")
                or soup.select("div[class*='product-base']")
            )
            for card in cards:
                title_node = (
                    card.select_one("h4.product-product")
                    or card.select_one("h3.product-brand")
                    or card.select_one("div.product-brand")
                )
                if not title_node:
                    continue
                brand_node = card.select_one("h3.product-brand")
                title = title_node.get_text(strip=True)
                if brand_node and brand_node != title_node:
                    title = f"{brand_node.get_text(strip=True)} {title}"

                price_node = (
                    card.select_one("span.product-discountedPrice")
                    or card.select_one("span.product-price")
                    or card.select_one("div.product-price")
                )
                if not price_node:
                    continue
                clean_p = re.sub(r"(?i)\b(?:rs\.?|inr)\b|[\u20b9₹]", "", price_node.get_text(strip=True)).replace(",", "")
                match = re.search(r"(\d+(?:\.\d+)?)", clean_p)
                if not match:
                    continue
                try:
                    price = float(match.group(1))
                except ValueError:
                    continue
                if price <= 0:
                    continue

                score = self.compute_match_score(
                    title, target_name, brand, barcode,
                    catalog_price=catalog_price, scraped_price=price
                )
                if score < MATCH_THRESHOLD:
                    continue

                mrp = None
                mrp_node = card.select_one("span.product-strike")
                if mrp_node:
                    clean_m = re.sub(r"(?i)\b(?:rs\.?|inr)\b|[\u20b9₹]", "", mrp_node.get_text(strip=True)).replace(",", "")
                    match_m = re.search(r"(\d+(?:\.\d+)?)", clean_m)
                    if match_m:
                        try:
                            mrp_val = float(match_m.group(1))
                            if mrp_val >= price:
                                mrp = mrp_val
                        except ValueError:
                            pass

                link_node = card.select_one("a[href]")
                href = link_node.get("href", "") if link_node else ""
                prod_url = search_url
                url_verified = False
                if href:
                    clean_href = href.split("?")[0].lstrip("/")
                    prod_url = f"https://www.myntra.com/{clean_href}"
                    url_verified = True

                if catalog_price > 0:
                    diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                    rank = score - (0.25 * diff_ratio)
                else:
                    rank = score

                if rank > best_rank:
                    best_rank = rank
                    best_candidate = {
                        "platform": "Myntra",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }
            return best_candidate
        except Exception as e:
            logger.debug(f"[Myntra] DOM parse error: {e}")
            return None


class AjioScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Ajio",
            search_url_template="https://www.ajio.com/search/?text={query}",
            base_url="https://www.ajio.com",
        )

    async def _tier1_internal_api(
        self, product_name: str, brand: str, barcode: str, catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Query Ajio search API for structured product JSON."""
        from urllib.parse import quote_plus
        from curl_cffi.requests import AsyncSession

        query = self.clean_search_query(product_name, brand)
        api_url = (
            f"https://www.ajio.com/api/search?fields=SITE&currentPage=0&pageSize=20"
            f"&format=json&query={quote_plus(query)}%3Arelevance&text={quote_plus(query)}"
        )
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Referer": f"https://www.ajio.com/search/?text={quote_plus(query)}",
        }
        try:
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(api_url, headers=headers, timeout=12)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200:
                    data = resp.json()
                    products = data.get("products", [])
                    best_candidate = None
                    best_rank = -1.0
                    for p in products:
                        name = p.get("name", "")
                        b = p.get("fnlColorVariantData", {}).get("brandName", "") or brand
                        title = f"{b} {name}".strip() if b and b.lower() not in name.lower() else name
                        price_dict = p.get("price", {})
                        try:
                            price = float(price_dict.get("value", 0.0) if isinstance(price_dict, dict) else (p.get("price") or 0.0))
                        except (ValueError, TypeError):
                            continue
                        if price <= 0:
                            continue

                        was_price_dict = p.get("wasPriceData", {})
                        try:
                            mrp = float(was_price_dict.get("value", 0.0) if isinstance(was_price_dict, dict) else (p.get("wasPriceData") or 0.0)) or None
                        except (ValueError, TypeError):
                            mrp = None

                        score = self.compute_match_score(
                            title, product_name, brand, barcode,
                            catalog_price=catalog_price, scraped_price=price
                        )
                        if score < MATCH_THRESHOLD:
                            continue

                        url_path = p.get("url", "")
                        prod_url = f"https://www.ajio.com{url_path}" if url_path.startswith("/") else url_path or self.base_url

                        if catalog_price > 0:
                            diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                            rank = score - (0.25 * diff_ratio)
                        else:
                            rank = score

                        if rank > best_rank:
                            best_rank = rank
                            best_candidate = {
                                "platform": "Ajio",
                                "price": price,
                                "mrp": mrp if mrp and mrp >= price else None,
                                "currency": "INR",
                                "in_stock": True,
                                "stock_status": "in_stock",
                                "product_url": prod_url,
                                "url_verified": bool(url_path),
                                "product_title": self.sanitize_output(title),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "match_score": score,
                                "unverified_match": False,
                                "scrape_mode": "internal_api",
                                "data_source": "live_scrape",
                            }
                    if best_candidate:
                        return best_candidate
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.debug(f"[Ajio] API search error: {e}")
        return None

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """DOM and preloaded state extraction from Ajio search result grid."""
        import json

        best_candidate = None
        best_rank = -1.0

        # 1. First check window.__PRELOADED_STATE__
        idx = html_text.find("window.__PRELOADED_STATE__ = ")
        if idx != -1:
            raw = html_text[idx + len("window.__PRELOADED_STATE__ = "):]
            end = raw.find("</script>")
            clean_json = raw[:end].strip().rstrip(";")
            try:
                data = json.loads(clean_json)
                entities = data.get("grid", {}).get("entities", {})
                items = entities.values() if isinstance(entities, dict) else (entities if isinstance(entities, list) else [])
                for item in items:
                    name = item.get("name", "")
                    b = item.get("fnlColorVariantData", {}).get("brandName", "") or brand
                    title = f"{b} {name}".strip() if b and b.lower() not in name.lower() else name
                    price_dict = item.get("price", {})
                    try:
                        price = float(price_dict.get("value", 0.0) if isinstance(price_dict, dict) else (item.get("price") or 0.0))
                    except (ValueError, TypeError):
                        continue
                    if price <= 0:
                        continue

                    was_dict = item.get("wasPriceData", {})
                    try:
                        mrp = float(was_dict.get("value", 0.0) if isinstance(was_dict, dict) else (item.get("wasPriceData") or 0.0)) or None
                    except (ValueError, TypeError):
                        mrp = None

                    score = self.compute_match_score(
                        title, target_name, brand, barcode,
                        catalog_price=catalog_price, scraped_price=price
                    )
                    if score < MATCH_THRESHOLD:
                        continue

                    url_path = item.get("url", "")
                    prod_url = f"https://www.ajio.com{url_path}" if url_path.startswith("/") else url_path or search_url

                    if catalog_price > 0:
                        diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                        rank = score - (0.25 * diff_ratio)
                    else:
                        rank = score

                    if rank > best_rank:
                        best_rank = rank
                        best_candidate = {
                            "platform": "Ajio",
                            "price": price,
                            "mrp": mrp if mrp and mrp >= price else None,
                            "currency": "INR",
                            "in_stock": True,
                            "stock_status": "in_stock",
                            "product_url": prod_url,
                            "url_verified": bool(url_path),
                            "product_title": self.sanitize_output(title),
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                            "match_score": score,
                            "unverified_match": False,
                            "scrape_mode": "mobile_headers",
                            "data_source": "live_scrape",
                        }
                if best_candidate:
                    return best_candidate
            except Exception as jex:
                logger.debug(f"[Ajio] __PRELOADED_STATE__ parse error: {jex}")

        # 2. Fall back to DOM parsing
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")

            cards = (
                soup.select("div.item")
                or soup.select("div.preview")
                or soup.select("div[class*='item']")
                or soup.select("div[class*='preview']")
            )
            for card in cards:
                title_node = (
                    card.select_one("div.nameCls")
                    or card.select_one("div.name")
                    or card.select_one("div[class*='name']")
                )
                brand_node = card.select_one("div.brand") or card.select_one("div[class*='brand']")
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)
                if brand_node:
                    b_text = brand_node.get_text(strip=True)
                    if b_text.lower() not in title.lower():
                        title = f"{b_text} {title}"

                price_node = (
                    card.select_one("span.price")
                    or card.select_one("span.fnl-plp-price")
                    or card.select_one("div.price")
                    or card.select_one("span[class*='price']")
                )
                if not price_node:
                    continue
                clean_p = re.sub(r"(?i)\b(?:rs\.?|inr)\b|[\u20b9₹]", "", price_node.get_text(strip=True)).replace(",", "")
                match = re.search(r"(\d+(?:\.\d+)?)", clean_p)
                if not match:
                    continue
                try:
                    price = float(match.group(1))
                except ValueError:
                    continue
                if price <= 0:
                    continue

                score = self.compute_match_score(
                    title, target_name, brand, barcode,
                    catalog_price=catalog_price, scraped_price=price
                )
                if score < MATCH_THRESHOLD:
                    continue

                mrp = None
                mrp_node = card.select_one("span.orginal-price") or card.select_one("span.fnl-original-price") or card.select_one("span.strike")
                if mrp_node:
                    clean_m = re.sub(r"(?i)\b(?:rs\.?|inr)\b|[\u20b9₹]", "", mrp_node.get_text(strip=True)).replace(",", "")
                    match_m = re.search(r"(\d+(?:\.\d+)?)", clean_m)
                    if match_m:
                        try:
                            mrp_val = float(match_m.group(1))
                            if mrp_val >= price:
                                mrp = mrp_val
                        except ValueError:
                            pass

                link_node = card.select_one("a[href]") or card.find("a", href=True)
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"].split("?")[0]
                    if href.startswith("/"):
                        prod_url = f"https://www.ajio.com{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if catalog_price > 0:
                    diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                    rank = score - (0.25 * diff_ratio)
                else:
                    rank = score

                if rank > best_rank:
                    best_rank = rank
                    best_candidate = {
                        "platform": "Ajio",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }
            return best_candidate
        except Exception as e:
            logger.debug(f"[Ajio] DOM parse error: {e}")
            return None


class NykaaScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Nykaa",
            search_url_template="https://www.nykaa.com/search/result/?q={query}",
            base_url="https://www.nykaa.com",
        )

    async def _tier1_internal_api(
        self, product_name: str, brand: str, barcode: str, catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Query Nykaa search page and extract __PRELOADED_STATE__ structured JSON."""
        from urllib.parse import quote_plus
        from curl_cffi.requests import AsyncSession

        query = self.clean_search_query(product_name, brand)
        search_url = f"https://www.nykaa.com/search/result/?q={quote_plus(query)}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Referer": "https://www.nykaa.com/",
        }
        try:
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(search_url, headers=headers, timeout=12)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200:
                    cand = self._extract_from_preloaded_state(
                        resp.text, product_name, brand, barcode, search_url, catalog_price
                    )
                    if cand:
                        cand["scrape_mode"] = "internal_api"
                        return cand
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.debug(f"[Nykaa] tier1 internal_api error: {e}")
        return None

    def _extract_from_preloaded_state(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """Extract products from window.__PRELOADED_STATE__ in Nykaa HTML."""
        import json

        idx = html_text.find("window.__PRELOADED_STATE__")
        if idx == -1:
            return None

        brace_idx = html_text.find("{", idx)
        if brace_idx == -1:
            return None

        try:
            data, _ = json.JSONDecoder().raw_decode(html_text[brace_idx:])
        except Exception as e:
            logger.debug(f"[Nykaa] __PRELOADED_STATE__ raw_decode error: {e}")
            return None

        products = (
            data.get("searchListingPage", {}).get("listingData", {}).get("products")
            or data.get("searchReducer", {}).get("searchListing", {}).get("products")
            or data.get("searchListing", {}).get("products")
            or []
        )
        if not products:
            return None

        best_candidate = None
        best_rank = -1.0

        for p in products:
            title = p.get("title") or p.get("name") or p.get("productTitle") or ""
            if not title:
                continue
            if brand and brand.lower() not in title.lower():
                title = f"{brand} {title}"

            try:
                price = float(p.get("final_price") or p.get("offer_price") or p.get("price") or 0.0)
            except (ValueError, TypeError):
                continue
            if price <= 0:
                continue

            try:
                mrp = float(p.get("mrp") or 0.0) or None
            except (ValueError, TypeError):
                mrp = None

            score = self.compute_match_score(
                title, target_name, brand, barcode,
                catalog_price=catalog_price, scraped_price=price
            )
            if score < MATCH_THRESHOLD:
                continue

            slug = p.get("slug") or p.get("product_url") or p.get("actionUrl") or ""
            pid = p.get("id") or p.get("productId") or ""
            if slug:
                clean_slug = slug.lstrip("/")
                if clean_slug.startswith("http"):
                    prod_url = clean_slug
                elif "/p/" in clean_slug:
                    prod_url = f"https://www.nykaa.com/{clean_slug}"
                elif pid:
                    prod_url = f"https://www.nykaa.com/{clean_slug}/p/{pid}"
                else:
                    prod_url = f"https://www.nykaa.com/{clean_slug}"
                url_verified = True
            elif pid:
                prod_url = f"https://www.nykaa.com/p/{pid}"
                url_verified = True
            else:
                prod_url = search_url
                url_verified = False

            in_stock = p.get("inStock", True)
            if isinstance(in_stock, bool) and not in_stock:
                stock_status = "out_of_stock"
            elif p.get("quantity") is not None and p.get("quantity") <= 0:
                stock_status = "out_of_stock"
            else:
                stock_status = "in_stock"

            if catalog_price > 0:
                diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                rank = score - (0.25 * diff_ratio)
            else:
                rank = score

            if rank > best_rank:
                best_rank = rank
                best_candidate = {
                    "platform": "Nykaa",
                    "price": price,
                    "mrp": mrp if mrp and mrp >= price else None,
                    "currency": "INR",
                    "in_stock": (stock_status == "in_stock"),
                    "stock_status": stock_status,
                    "product_url": prod_url,
                    "url_verified": url_verified,
                    "product_title": self.sanitize_output(title),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "match_score": score,
                    "unverified_match": False,
                    "scrape_mode": "mobile_headers",
                    "data_source": "live_scrape",
                }

        return best_candidate

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Parse Nykaa product cards via structured data, __PRELOADED_STATE__, or DOM."""
        # 1. First delegate to universal structured data (JSON-LD / Next.js)
        structured = self._extract_structured_data(
            html_text, target_name, brand, barcode, search_url, catalog_price=catalog_price
        )
        if structured:
            return structured

        # 2. Check window.__PRELOADED_STATE__
        cand = self._extract_from_preloaded_state(
            html_text, target_name, brand, barcode, search_url, catalog_price=catalog_price
        )
        if cand:
            return cand

        # 3. Fall back to DOM card selectors
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_rank = -1.0

            cards = (
                soup.select("div.productWrapper")
                or soup.select("div[data-test-id='product-card']")
                or soup.select("div[class*='productCard']")
                or soup.select("div[class*='product-wrapper']")
                or soup.select("a[href*='/p/']")
            )
            for card in cards:
                title_node = (
                    card.select_one("div.css-xrzmfa")
                    or card.select_one("div[class*='title']")
                    or card.select_one("a.css-qlopj5")
                    or card.find("a", href=True)
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)

                price_node = (
                    card.select_one("span.css-111z9ua")
                    or card.select_one("span[class*='price']")
                    or card.select_one("span.css-17x46n5")
                )
                if not price_node:
                    continue
                clean_p = re.sub(r"[^\d.]", "", price_node.get_text(strip=True).replace(",", ""))
                try:
                    price = float(clean_p)
                except ValueError:
                    continue
                if price <= 0:
                    continue

                score = self.compute_match_score(
                    title, target_name, brand, barcode,
                    catalog_price=catalog_price, scraped_price=price
                )
                if score < MATCH_THRESHOLD:
                    continue

                mrp = None
                mrp_node = card.select_one("span.css-17x46n5, span[class*='mrp']")
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                link_node = (
                    card.select_one("a.css-qlopj5[href]")
                    or card.select_one("a[href*='/p/']")
                    or card.find("a", href=True)
                )
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"].split("?")[0]
                    if href.startswith("/"):
                        prod_url = f"https://www.nykaa.com{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if catalog_price > 0:
                    diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                    rank = score - (0.25 * diff_ratio)
                else:
                    rank = score

                if rank > best_rank:
                    best_rank = rank
                    best_candidate = {
                        "platform": "Nykaa",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }
            return best_candidate
        except Exception as e:
            logger.debug(f"[Nykaa] DOM parse error: {e}")
            return None


class PurplleScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Purplle",
            search_url_template="https://www.purplle.com/search?q={query}",
            base_url="https://www.purplle.com",
        )

    async def _tier1_internal_api(
        self, product_name: str, brand: str, barcode: str, catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Query Purplle internal search API for items."""
        from urllib.parse import quote_plus
        from curl_cffi.requests import AsyncSession

        query = self.clean_search_query(product_name, brand)
        api_url = f"https://www.purplle.com/api/shop/itemsv3?search={quote_plus(query)}&page=1&device=desktop"
        headers = {
            "Origin": "https://www.purplle.com",
            "Referer": f"https://www.purplle.com/search?q={quote_plus(query)}",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        try:
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(api_url, headers=headers, timeout=12)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200 and resp.text.strip():
                    try:
                        data = resp.json()
                    except Exception:
                        data = None
                    if data:
                        items = (
                            data.get("items")
                            or data.get("products")
                            or data.get("data")
                            or (data if isinstance(data, list) else [])
                        )
                        best_candidate = None
                        best_rank = -1.0
                        for it in items:
                            title = it.get("name") or it.get("item_name") or it.get("title") or ""
                            if not title:
                                continue
                            if brand and brand.lower() not in title.lower():
                                title = f"{brand} {title}"

                            try:
                                price = float(it.get("our_price") or it.get("offer_price") or it.get("price") or it.get("special_price") or 0.0)
                            except (ValueError, TypeError):
                                continue
                            if price <= 0:
                                continue

                            try:
                                mrp = float(it.get("mrp") or it.get("actual_price") or 0.0) or None
                            except (ValueError, TypeError):
                                mrp = None

                            score = self.compute_match_score(
                                title, product_name, brand, barcode,
                                catalog_price=catalog_price, scraped_price=price
                            )
                            if score < MATCH_THRESHOLD:
                                continue

                            slug = it.get("slug") or it.get("url") or it.get("product_url") or ""
                            if slug:
                                clean_slug = slug.lstrip("/")
                                if clean_slug.startswith("http"):
                                    prod_url = clean_slug
                                elif clean_slug.startswith("product/"):
                                    prod_url = f"https://www.purplle.com/{clean_slug}"
                                else:
                                    prod_url = f"https://www.purplle.com/product/{clean_slug}"
                                url_verified = True
                            else:
                                prod_url = self.base_url
                                url_verified = False

                            stock_status = "in_stock" if it.get("in_stock", True) else "out_of_stock"

                            if catalog_price > 0:
                                diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                                rank = score - (0.25 * diff_ratio)
                            else:
                                rank = score

                            if rank > best_rank:
                                best_rank = rank
                                best_candidate = {
                                    "platform": "Purplle",
                                    "price": price,
                                    "mrp": mrp if mrp and mrp >= price else None,
                                    "currency": "INR",
                                    "in_stock": (stock_status == "in_stock"),
                                    "stock_status": stock_status,
                                    "product_url": prod_url,
                                    "url_verified": url_verified,
                                    "product_title": self.sanitize_output(title),
                                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                                    "match_score": score,
                                    "unverified_match": False,
                                    "scrape_mode": "internal_api",
                                    "data_source": "live_scrape",
                                }
                        if best_candidate:
                            return best_candidate
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.debug(f"[Purplle] tier1 internal_api error: {e}")
        return None

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Extract Purplle product card via structured data or DOM."""
        # 1. First delegate to universal structured data (JSON-LD / Next.js)
        structured = self._extract_structured_data(
            html_text, target_name, brand, barcode, search_url, catalog_price=catalog_price
        )
        if structured:
            return structured

        # 2. Parse DOM product cards
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_rank = -1.0

            cards = (
                soup.select("div.product-card")
                or soup.select("div[class*='product-card']")
                or soup.select("div.item")
                or soup.select("a[href*='/product/']")
            )
            for card in cards:
                title_node = (
                    card.select_one("p.title")
                    or card.select_one("a.title")
                    or card.select_one("div[class*='title']")
                    or card.select_one("span[class*='title']")
                    or card.find("a", href=True)
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)

                price_node = (
                    card.select_one("span.price")
                    or card.select_one("span.actual-price")
                    or card.select_one("span[class*='price']")
                    or card.select_one("div.price")
                )
                if not price_node:
                    continue
                clean_p = re.sub(r"[^\d.]", "", price_node.get_text(strip=True).replace(",", ""))
                try:
                    price = float(clean_p)
                except ValueError:
                    continue
                if price <= 0:
                    continue

                score = self.compute_match_score(
                    title, target_name, brand, barcode,
                    catalog_price=catalog_price, scraped_price=price
                )
                if score < MATCH_THRESHOLD:
                    continue

                mrp = None
                mrp_node = card.select_one("span.mrp, span.old-price, span[class*='mrp']")
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                link_node = card if card.name == "a" and card.get("href") else (card.select_one("a[href*='/product/']") or card.find("a", href=True))
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"].split("?")[0]
                    if href.startswith("/"):
                        prod_url = f"https://www.purplle.com{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if catalog_price > 0:
                    diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                    rank = score - (0.25 * diff_ratio)
                else:
                    rank = score

                if rank > best_rank:
                    best_rank = rank
                    best_candidate = {
                        "platform": "Purplle",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }
            return best_candidate
        except Exception as e:
            logger.debug(f"[Purplle] DOM parse error: {e}")
            return None


class BigBasketScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="BigBasket",
            search_url_template="https://www.bigbasket.com/ps/?q={query}",
            base_url="https://www.bigbasket.com",
        )
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
        }

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str) -> Optional[Dict[str, Any]]:
        """BigBasket 2.0 search endpoint with cookie bootstrap & dual-schema parsing."""
        from datetime import datetime, timezone
        from urllib.parse import quote_plus
        from curl_cffi.requests import AsyncSession

        clean_query = self.clean_search_query(product_name, brand)
        if not clean_query:
            clean_query = product_name

        headers = dict(self.headers)
        headers["X-Channel"] = "BB-WEB"
        headers["Referer"] = f"https://www.bigbasket.com/ps/?q={quote_plus(clean_query)}"

        api_url = f"https://www.bigbasket.com/listing-svc/v2/products?type=pc&slug={quote_plus(clean_query)}&page=1"
        try:
            async with AsyncSession(impersonate="chrome124") as session:
                # Step 1: Bootstrap visitor cookies
                try:
                    boot_resp = await session.get("https://www.bigbasket.com/", headers=self.headers, timeout=8)
                    self.check_bot_detection(boot_resp.status_code, boot_resp.text)
                except (PlatformRateLimitError, BotDetectionEncountered) as bde:
                    raise bde
                except Exception:
                    pass

                # Step 2: Query BigBasket 2.0 listing API
                resp = await session.get(api_url, headers=headers, timeout=10)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200:
                    data = resp.json()
                    # Check BB2.0 tabs[0].product_info.products or legacy tab.product_info.products
                    products = []
                    tabs = data.get("tabs", [])
                    if tabs and isinstance(tabs, list) and len(tabs) > 0:
                        products = tabs[0].get("product_info", {}).get("products", [])
                    if not products and "tab" in data:
                        tab_obj = data.get("tab", {})
                        if isinstance(tab_obj, dict):
                            products = tab_obj.get("product_info", {}).get("products", [])

                    best_candidate = None
                    best_score = 0.0
                    for p in products:
                        # Extract title
                        brand_obj = p.get("brand", {})
                        brand_name = brand_obj.get("name") if isinstance(brand_obj, dict) else str(brand_obj or "")
                        desc = p.get("desc") or p.get("p_desc") or p.get("name") or ""
                        if brand_name and brand_name.lower() not in desc.lower():
                            title = f"{brand_name} {desc}".strip()
                        else:
                            title = desc
                        if not title:
                            continue

                        score = self.compute_match_score(title, product_name, brand, barcode)
                        if score < MATCH_THRESHOLD:
                            continue

                        # Extract price (BB2.0 pricing.discount.prim_price.sp vs legacy sp)
                        pricing = p.get("pricing", {})
                        discount = pricing.get("discount", {}) if isinstance(pricing, dict) else {}
                        prim_price = discount.get("prim_price", {}) if isinstance(discount, dict) else {}

                        sp_raw = (
                            prim_price.get("sp") or
                            (discount.get("sp") if isinstance(discount, dict) else None) or
                            (pricing.get("sp") if isinstance(pricing, dict) else None) or
                            p.get("sp")
                        )
                        if not sp_raw:
                            continue
                        clean_p = re.sub(r"[^\d.]", "", str(sp_raw).replace(",", ""))
                        try:
                            price = float(clean_p)
                        except (ValueError, TypeError):
                            continue
                        if price <= 0:
                            continue

                        # Extract MRP
                        mrp_raw = (
                            (discount.get("mrp") if isinstance(discount, dict) else None) or
                            (pricing.get("mrp") if isinstance(pricing, dict) else None) or
                            p.get("mrp")
                        )
                        mrp = None
                        if mrp_raw:
                            clean_m = re.sub(r"[^\d.]", "", str(mrp_raw).replace(",", ""))
                            try:
                                mrp_val = float(clean_m)
                                if mrp_val >= price:
                                    mrp = mrp_val
                            except (ValueError, TypeError):
                                pass

                        pid = p.get("id") or p.get("p_id")
                        slug = p.get("slug")
                        if pid and slug:
                            p_url = f"https://www.bigbasket.com/pd/{pid}/{slug}/"
                        elif pid:
                            p_url = f"https://www.bigbasket.com/pd/{pid}"
                        else:
                            p_url = f"https://www.bigbasket.com/ps/?q={quote_plus(clean_query)}"

                        in_stock = True
                        if "availability" in p and isinstance(p["availability"], dict):
                            in_stock = p["availability"].get("is_in_stock", True)
                        elif "is_sold_out" in p:
                            in_stock = not p.get("is_sold_out", False)

                        if score > best_score:
                            best_score = score
                            best_candidate = {
                                "platform": "BigBasket",
                                "price": price,
                                "mrp": mrp,
                                "currency": "INR",
                                "in_stock": in_stock,
                                "stock_status": "in_stock" if in_stock else "out_of_stock",
                                "product_url": p_url,
                                "url_verified": bool(pid),
                                "product_title": self.sanitize_output(title),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "match_score": score,
                                "unverified_match": False,
                                "scrape_mode": "internal_api",
                                "data_source": "live_scrape",
                            }

                    if best_candidate:
                        return best_candidate
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.warning(f"[BigBasket] API error: {e}")

        return None

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """Extract products from __NEXT_DATA__ or DOM cards on BigBasket search result page."""
        try:
            # 1. Structured data / Next data delegation
            struct_candidate = self._extract_structured_data(
                html_text, target_name, brand, barcode, search_url
            )
            if struct_candidate:
                struct_candidate["scrape_mode"] = "mobile_headers"
                struct_candidate["stock_status"] = "in_stock" if struct_candidate.get("in_stock", True) else "out_of_stock"
                return struct_candidate

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")

            # 2. Direct __NEXT_DATA__ extraction for BigBasket 2.0 Next.js schema
            next_script = soup.find("script", id="__NEXT_DATA__")
            if next_script and (next_script.string or next_script.text):
                try:
                    next_json = json.loads(next_script.string or next_script.text)
                    page_props = next_json.get("props", {}).get("pageProps", {})
                    products = []
                    init_data = page_props.get("initialData", {})
                    if isinstance(init_data, dict):
                        tabs = init_data.get("tabs", [])
                        if tabs and isinstance(tabs, list) and len(tabs) > 0:
                            products = tabs[0].get("product_info", {}).get("products", [])
                    if not products and "tabs" in page_props:
                        tabs = page_props.get("tabs", [])
                        if tabs and isinstance(tabs, list) and len(tabs) > 0:
                            products = tabs[0].get("product_info", {}).get("products", [])

                    best_c = None
                    best_s = 0.0
                    for p in products:
                        brand_obj = p.get("brand", {})
                        brand_name = brand_obj.get("name") if isinstance(brand_obj, dict) else str(brand_obj or "")
                        desc = p.get("desc") or p.get("p_desc") or p.get("name") or ""
                        if brand_name and brand_name.lower() not in desc.lower():
                            t = f"{brand_name} {desc}".strip()
                        else:
                            t = desc
                        if not t:
                            continue
                        sc = self.compute_match_score(t, target_name, brand, barcode)
                        if sc < MATCH_THRESHOLD:
                            continue
                        pricing = p.get("pricing", {})
                        discount = pricing.get("discount", {}) if isinstance(pricing, dict) else {}
                        prim_price = discount.get("prim_price", {}) if isinstance(discount, dict) else {}
                        sp_raw = prim_price.get("sp") or discount.get("sp") or pricing.get("sp") or p.get("sp")
                        if not sp_raw:
                            continue
                        clean_p = re.sub(r"[^\d.]", "", str(sp_raw).replace(",", ""))
                        try:
                            pr = float(clean_p)
                        except (ValueError, TypeError):
                            continue
                        if pr <= 0:
                            continue

                        mrp_raw = discount.get("mrp") or pricing.get("mrp") or p.get("mrp")
                        mrp_val = None
                        if mrp_raw:
                            clean_m = re.sub(r"[^\d.]", "", str(mrp_raw).replace(",", ""))
                            try:
                                mv = float(clean_m)
                                if mv >= pr:
                                    mrp_val = mv
                            except (ValueError, TypeError):
                                pass

                        pid = p.get("id") or p.get("p_id")
                        slug = p.get("slug")
                        url = f"https://www.bigbasket.com/pd/{pid}/{slug}/" if pid and slug else (
                            f"https://www.bigbasket.com/pd/{pid}" if pid else search_url
                        )
                        in_stock = True
                        if "availability" in p and isinstance(p["availability"], dict):
                            in_stock = p["availability"].get("is_in_stock", True)
                        elif "is_sold_out" in p:
                            in_stock = not p.get("is_sold_out", False)

                        if sc > best_s:
                            best_s = sc
                            best_c = {
                                "platform": "BigBasket",
                                "price": pr,
                                "mrp": mrp_val,
                                "currency": "INR",
                                "in_stock": in_stock,
                                "stock_status": "in_stock" if in_stock else "out_of_stock",
                                "product_url": url,
                                "url_verified": bool(pid),
                                "product_title": self.sanitize_output(t),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "match_score": sc,
                                "unverified_match": False,
                                "scrape_mode": "mobile_headers",
                                "data_source": "live_scrape",
                            }
                    if best_c:
                        return best_c
                except Exception as ex:
                    logger.debug(f"[BigBasket] __NEXT_DATA__ error: {ex}")

            # 3. DOM selectors fallback
            best_candidate = None
            best_score = 0.0
            cards = (
                soup.select("div[class*='SKUDeck___StyledDiv']")
                or soup.select("li[class*='PaginateItems___StyledLi']")
                or soup.select("div.product-deck")
                or soup.select("div[class*='ProductDeck']")
            )
            for card in cards:
                title_node = (
                    card.select_one("h3[class*='Label-sc']")
                    or card.select_one("div[class*='product-title']")
                    or card.select_one("h3")
                    or card.find("a", href=True)
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)
                score = self.compute_match_score(title, target_name, brand, barcode)
                if score < MATCH_THRESHOLD:
                    continue

                price_node = (
                    card.select_one("span[class*='Pricing___StyledLabel']")
                    or card.select_one("span.discnt-price")
                    or card.select_one("span[class*='Pricing']")
                    or card.select_one("span[class*='Price']")
                )
                if not price_node:
                    continue
                clean_p = re.sub(r"[^\d.]", "", price_node.get_text(strip=True).replace(",", ""))
                try:
                    price = float(clean_p)
                except ValueError:
                    continue
                if price <= 0:
                    continue

                mrp = None
                mrp_node = card.select_one("span[class*='Pricing___StyledLabel2'], span.was-price")
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                link_node = card.select_one("a[href*='/pd/']") or card.find("a", href=True)
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"].split("?")[0]
                    if href.startswith("/"):
                        prod_url = f"https://www.bigbasket.com{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "BigBasket",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }
            return best_candidate
        except Exception as e:
            logger.debug(f"[BigBasket] DOM parse error: {e}")
            return None


class JioMartScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="JioMart",
            search_url_template="https://www.jiomart.com/search/{query}",
            base_url="https://www.jiomart.com",
        )
        self.pincode_cookies = {
            "nms_mgo_pincode": "400020",
            "nms_mgo_city": "Mumbai",
            "nms_mgo_state_code": "MH",
        }

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str, catalog_price: float = 0.0, *args, **kwargs) -> Optional[Dict[str, Any]]:
        """JioMart Fynd catalog JSON extraction with Mumbai pincode location headers via curl_cffi."""
        from urllib.parse import quote_plus
        from curl_cffi.requests import AsyncSession

        clean_query = self.clean_search_query(product_name, brand)
        if not clean_query:
            clean_query = product_name

        api_url = f"https://www.jiomart.com/service/application/catalog/v1.0/products?q={quote_plus(clean_query)}"
        headers = {
            "x-application-id": "685945f46c8c7aee3f3af605",
            "x-application-token": "TpKw7wD9h",
            "x-location-detail": json.dumps({"pincode": "400020"}),
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Referer": "https://www.jiomart.com/",
        }
        try:
            async with AsyncSession(impersonate="chrome124", cookies=self.pincode_cookies) as session:
                resp = await session.get(api_url, headers=headers, timeout=12)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", [])
                    best_candidate = None
                    best_score = 0.0

                    for it in items:
                        name = it.get("name")
                        if not name:
                            continue
                        score = self.compute_match_score(
                            name, product_name, brand, barcode,
                            catalog_price=catalog_price
                        )
                        if score < MATCH_THRESHOLD:
                            continue

                        price_obj = it.get("price", {})
                        eff = price_obj.get("effective", {})
                        p_val = eff.get("min") if isinstance(eff, dict) else eff
                        if not p_val:
                            continue
                        clean_p = re.sub(r"[^\d.]", "", str(p_val).replace(",", ""))
                        try:
                            price = float(clean_p)
                        except (ValueError, TypeError):
                            continue
                        if price <= 0:
                            continue

                        if catalog_price > 0 and (price < (catalog_price * 0.20) or price > (catalog_price * 5.0)):
                            continue

                        marked = price_obj.get("marked", {})
                        m_val = marked.get("min") if isinstance(marked, dict) else marked
                        mrp = None
                        if m_val:
                            try:
                                mrp_num = float(re.sub(r"[^\d.]", "", str(m_val).replace(",", "")))
                                if mrp_num >= price:
                                    mrp = mrp_num
                            except (ValueError, TypeError):
                                pass

                        slug = it.get("slug")
                        prod_url = f"https://www.jiomart.com/product/{slug}" if slug else self.base_url
                        url_verified = bool(slug)

                        if score > best_score:
                            best_score = score
                            best_candidate = {
                                "platform": "JioMart",
                                "price": price,
                                "mrp": mrp,
                                "currency": "INR",
                                "in_stock": True,
                                "stock_status": "in_stock",
                                "product_url": prod_url,
                                "url_verified": url_verified,
                                "product_title": self.sanitize_output(name),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "match_score": score,
                                "unverified_match": False,
                                "scrape_mode": "internal_api",
                                "data_source": "live_scrape",
                            }

                    if best_candidate:
                        return best_candidate

                # Fallback to search HTML parsing if catalog API had no items
                search_url = f"https://www.jiomart.com/search/{quote_plus(clean_query)}"
                search_headers = {
                    "User-Agent": headers["User-Agent"],
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-IN,en;q=0.9",
                }
                resp_html = await session.get(search_url, headers=search_headers, timeout=12)
                self.check_bot_detection(resp_html.status_code, resp_html.text)
                if resp_html.status_code == 200:
                    cand = self._extract_structured_data(resp_html.text, product_name, brand, barcode, search_url, catalog_price=catalog_price)
                    if not cand:
                        cand = self._extract_cards(resp_html.text, product_name, brand, barcode, search_url)
                    if cand:
                        cand["scrape_mode"] = "internal_api"
                        return cand
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.warning(f"[JioMart] Tier 1 API error: {e}")

        return None

    async def _tier3_playwright(
        self, task_id: str, product_id: str, organization_id: str,
        product_name: str, brand: str, barcode: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """JioMart Playwright stealth with Mumbai pincode cookies and Algolia XHR interception."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return None

        from urllib.parse import quote
        clean_query = self.clean_search_query(product_name, brand)
        if not clean_query:
            clean_query = product_name
        search_url = f"https://www.jiomart.com/search/{quote(clean_query)}"
        try:
            validate_outbound_url(search_url)
        except ValueError:
            return None

        sem = _get_playwright_semaphore()
        candidate = None
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
                    ],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    ),
                    locale="en-IN",
                    viewport={"width": 1366, "height": 768},
                    timezone_id="Asia/Kolkata",
                    geolocation={"latitude": 18.9220, "longitude": 72.8347},
                    permissions=["geolocation"],
                )
                await context.add_cookies([
                    {"name": "nms_mgo_pincode", "value": "400020", "domain": ".jiomart.com", "path": "/"},
                    {"name": "nms_mgo_city", "value": "Mumbai", "domain": ".jiomart.com", "path": "/"},
                    {"name": "nms_mgo_state_code", "value": "MH", "domain": ".jiomart.com", "path": "/"},
                ])
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                """)
                page = await context.new_page()

                intercepted_hits = []
                async def on_response(response):
                    u = response.url.lower()
                    if any(term in u for term in ["algolia", "search", "1/indexes", "catalog"]) and response.status == 200:
                        try:
                            ct = response.headers.get("content-type", "")
                            if "json" in ct:
                                body = await response.json()
                                if isinstance(body, dict):
                                    if "results" in body and isinstance(body["results"], list):
                                        for r in body["results"]:
                                            if isinstance(r, dict) and "hits" in r:
                                                intercepted_hits.extend(r["hits"])
                                    elif "hits" in body and isinstance(body["hits"], list):
                                        intercepted_hits.extend(body["hits"])
                        except Exception:
                            pass

                page.on("response", on_response)
                await page.goto(search_url, timeout=25000, wait_until="domcontentloaded")
                try:
                    await page.wait_for_selector(".ais-InfiniteHits-item, .plp-card-details-name", timeout=6000)
                except Exception:
                    pass

                # 1. Parse intercepted Algolia hits
                best_score = 0.0
                for hit in intercepted_hits:
                    title = hit.get("name") or hit.get("display_name") or hit.get("title")
                    if not title:
                        continue
                    score = self.compute_match_score(title, product_name, brand, barcode)
                    if score < MATCH_THRESHOLD:
                        continue
                    price_val = hit.get("price") or hit.get("final_price") or hit.get("sp") or hit.get("selling_price")
                    if not price_val:
                        continue
                    clean_p = re.sub(r"[^\d.]", "", str(price_val).replace(",", ""))
                    try:
                        price = float(clean_p)
                    except ValueError:
                        continue
                    if price <= 0:
                        continue

                    mrp_val = hit.get("mrp") or hit.get("was_price")
                    mrp = None
                    if mrp_val:
                        clean_m = re.sub(r"[^\d.]", "", str(mrp_val).replace(",", ""))
                        try:
                            mrp_num = float(clean_m)
                            if mrp_num >= price:
                                mrp = mrp_num
                        except ValueError:
                            pass

                    url_path = hit.get("url_path") or hit.get("url") or hit.get("slug")
                    prod_url = f"https://www.jiomart.com{url_path}" if url_path and url_path.startswith("/") else (
                        url_path if url_path and url_path.startswith("http") else search_url
                    )

                    if score > best_score:
                        best_score = score
                        candidate = {
                            "platform": "JioMart",
                            "price": price,
                            "mrp": mrp,
                            "currency": "INR",
                            "in_stock": hit.get("in_stock", True),
                            "stock_status": "in_stock" if hit.get("in_stock", True) else "out_of_stock",
                            "product_url": prod_url,
                            "url_verified": bool(url_path),
                            "product_title": self.sanitize_output(title),
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                            "match_score": score,
                            "unverified_match": False,
                            "scrape_mode": "playwright",
                            "data_source": "live_scrape",
                        }

                # 2. DOM extraction fallback if Algolia didn't yield candidate
                if not candidate:
                    html_text = await page.content()
                    dom_cand = self._extract_cards(html_text, product_name, brand, barcode, search_url)
                    if dom_cand:
                        dom_cand["scrape_mode"] = "playwright"
                        candidate = dom_cand
            except Exception as e:
                logger.warning(f"[JioMart] Playwright tier 3 error: {e}")
            finally:
                if browser:
                    try: await browser.close()
                    except Exception: pass
                if pw_instance:
                    try: await pw_instance.stop()
                    except Exception: pass

        return candidate

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from JioMart search results."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = (
                soup.select("div.ais-InfiniteHits-item")
                or soup.select("li.ais-InfiniteHits-item")
                or soup.select("div.product-card")
                or soup.select("div[class*='product-card']")
                or soup.select("div.jm-col-3")
            )
            for card in cards:
                title_node = (
                    card.select_one("div.plp-card-details-name")
                    or card.select_one("div[class*='product-name']")
                    or card.select_one("div[class*='title']")
                    or card.find("a", href=True)
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)
                score = self.compute_match_score(title, target_name, brand, barcode)
                if score < MATCH_THRESHOLD:
                    continue

                price_node = (
                    card.select_one("span.jm-heading-xxs")
                    or card.select_one("span.final-price")
                    or card.select_one("span[class*='price']")
                )
                if not price_node:
                    continue
                clean_p = re.sub(r"[^\d.]", "", price_node.get_text(strip=True).replace(",", ""))
                try:
                    price = float(clean_p)
                except ValueError:
                    continue
                if price <= 0:
                    continue

                mrp = None
                mrp_node = card.select_one("span.jm-body-xxs, span.line-through, span[class*='mrp']")
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                link_node = card.select_one("a[href*='/p/']") or card.find("a", href=True)
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"].split("?")[0]
                    if href.startswith("/"):
                        prod_url = f"https://www.jiomart.com{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "JioMart",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }
            return best_candidate
        except Exception as e:
            logger.debug(f"[JioMart] DOM parse error: {e}")
            return None


class PepperfryScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Pepperfry",
            search_url_template="https://www.pepperfry.com/site_product/search?q={query}",
            base_url="https://www.pepperfry.com",
        )

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str, catalog_price: float = 0.0, *args, **kwargs) -> Optional[Dict[str, Any]]:
        """Pepperfry HTML & structured data extraction via curl_cffi."""
        from urllib.parse import quote_plus
        from curl_cffi.requests import AsyncSession

        clean_query = self.clean_search_query(product_name, brand)
        if not clean_query:
            clean_query = product_name

        search_url = f"https://www.pepperfry.com/site_product/search?q={quote_plus(clean_query)}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.pepperfry.com/",
        }
        try:
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(search_url, headers=headers, timeout=12)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200:
                    cand = self._extract_pepperfry_product_data(resp.text, product_name, brand, barcode, search_url, catalog_price=catalog_price)
                    if not cand:
                        cand = self._extract_structured_data(resp.text, product_name, brand, barcode, search_url, catalog_price=catalog_price)
                    if not cand:
                        cand = self._extract_cards(resp.text, product_name, brand, barcode, search_url)
                    if cand:
                        cand["scrape_mode"] = "internal_api"
                        return cand

                # Retry with relaxed query if original query was long and had no matches
                tokens = clean_query.split()
                if len(tokens) > 2:
                    relaxed_query = " ".join(tokens[:2])
                    relaxed_url = f"https://www.pepperfry.com/site_product/search?q={quote_plus(relaxed_query)}"
                    resp_retry = await session.get(relaxed_url, headers=headers, timeout=12)
                    self.check_bot_detection(resp_retry.status_code, resp_retry.text)
                    if resp_retry.status_code == 200:
                        cand_retry = self._extract_pepperfry_product_data(resp_retry.text, product_name, brand, barcode, relaxed_url, catalog_price=catalog_price)
                        if not cand_retry:
                            cand_retry = self._extract_cards(resp_retry.text, product_name, brand, barcode, relaxed_url)
                        if cand_retry:
                            cand_retry["scrape_mode"] = "internal_api"
                            return cand_retry
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.warning(f"[Pepperfry] Tier 1 API error: {e}")

        return None

    def _extract_pepperfry_product_data(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str, catalog_price: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """Extract products from embedded product_data JSON array in Pepperfry SSR HTML."""
        try:
            text = html_text.replace("&q;", '"')
            m = re.search(r'"product_data":\s*(\[\{.*?\}\])\s*,\s*"', text)
            if not m:
                return None
            prods = json.loads(m.group(1))
            best_candidate = None
            best_score = 0.0

            for p in prods:
                name = p.get("name") or p.get("title") or ""
                if not name:
                    continue
                brands_name = p.get("brands_name") or ""
                full_title = f"{brands_name} {name}".strip() if brands_name and brands_name.lower() not in name.lower() else name
                score = max(
                    self.compute_match_score(name, target_name, brand, barcode, catalog_price=catalog_price),
                    self.compute_match_score(full_title, target_name, brand, barcode, catalog_price=catalog_price),
                )
                if score < MATCH_THRESHOLD:
                    continue

                price_raw = p.get("you_pay_price") or p.get("price") or 0
                try:
                    price = float(price_raw)
                except (ValueError, TypeError):
                    continue
                if price <= 0:
                    continue

                if catalog_price > 0 and (price < (catalog_price * 0.20) or price > (catalog_price * 5.0)):
                    continue

                mrp_raw = p.get("price")
                mrp = None
                if mrp_raw:
                    try:
                        mrp_num = float(mrp_raw)
                        if mrp_num >= price:
                            mrp = mrp_num
                    except (ValueError, TypeError):
                        pass

                rel_url = p.get("url") or ""
                if rel_url.startswith("http"):
                    prod_url = rel_url
                elif rel_url:
                    prod_url = f"https://www.pepperfry.com/{rel_url.lstrip('/')}"
                else:
                    prod_url = search_url

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "Pepperfry",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": bool(rel_url),
                        "product_title": self.sanitize_output(full_title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "internal_api",
                        "data_source": "live_scrape",
                    }
            return best_candidate
        except Exception as e:
            logger.debug(f"[Pepperfry] product_data parsing error: {e}")
            return None

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from Pepperfry search results."""
        try:
            cand = self._extract_pepperfry_product_data(html_text, target_name, brand, barcode, search_url)
            if cand:
                return cand

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = (
                soup.select("pf-clip-product-card")
                or soup.select("div.clip-crd-10x11")
                or soup.select("div.clipCard")
                or soup.select("div.product-card")
                or soup.select("div[class*='clipCard']")
            )
            for card in cards:
                title_node = (
                    card.select_one("h2.product-name")
                    or card.select_one("div.product-name")
                    or card.select_one("h2.clipCard__title")
                    or card.select_one("a.clipCard__title")
                    or card.select_one("div[class*='title']")
                    or card.find("a", href=True)
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)
                brand_node = card.select_one("div.product-brand, div[class*='brand'], span[class*='brand']")
                brand_text = brand_node.get_text(strip=True) if brand_node else ""
                combined_title = f"{brand_text} {title}".strip() if brand_text else title

                score = max(
                    self.compute_match_score(title, target_name, brand, barcode),
                    self.compute_match_score(combined_title, target_name, brand, barcode),
                )
                if score < MATCH_THRESHOLD:
                    continue

                price_node = (
                    card.select_one("span.product-offer-price")
                    or card.select_one("span.clipCard__price--bold")
                    or card.select_one("span.offer-price")
                    or card.select_one("span.clipCard__price")
                    or card.select_one("span[class*='price']")
                )
                if not price_node:
                    continue
                clean_p = re.sub(r"[^\d.]", "", price_node.get_text(strip=True).replace(",", ""))
                try:
                    price = float(clean_p)
                except ValueError:
                    continue
                if price <= 0:
                    continue

                mrp = None
                mrp_node = card.select_one("span.product-mrp-price, span.clipCard__mrp, span[class*='mrp']")
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                link_node = (
                    card.select_one("a[href*='/product/']")
                    or card.select_one("a.clipCard__galleryWrap[href]")
                    or card.find("a", href=True)
                )
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"].split("?")[0]
                    if href.startswith("/"):
                        prod_url = f"https://www.pepperfry.com{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "Pepperfry",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }
            return best_candidate
        except Exception as e:
            logger.debug(f"[Pepperfry] DOM parse error: {e}")
            return None


class UrbanLadderScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Urban Ladder",
            search_url_template="https://www.urbanladder.com/products/search?keywords={query}",
            base_url="https://www.urbanladder.com",
        )

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str, catalog_price: float = 0.0, *args, **kwargs) -> Optional[Dict[str, Any]]:
        """Urban Ladder HTML & window.APP_DATA extraction via curl_cffi."""
        from urllib.parse import quote_plus
        from curl_cffi.requests import AsyncSession

        clean_query = self.clean_search_query(product_name, brand)
        if not clean_query:
            clean_query = product_name

        # Map common product tokens to known Urban Ladder category slugs
        slug_candidates = []
        q_lower = clean_query.lower()
        if any(w in q_lower for w in ["coffee", "center", "tea table"]):
            slug_candidates.extend(["coffee-table", "center-tables"])
        elif "chair" in q_lower:
            slug_candidates.extend(["office-chairs", "chairs"])
        elif "sofa" in q_lower:
            slug_candidates.extend(["sofas", "fabric-sofas"])
        elif "bed" in q_lower:
            slug_candidates.extend(["beds", "queen-size-beds"])
        elif "study" in q_lower or "desk" in q_lower:
            slug_candidates.extend(["study-tables"])
        elif "table" in q_lower:
            slug_candidates.extend(["coffee-table", "study-tables"])

        slug_candidates.append(f"products/search?q={quote_plus(clean_query)}")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.urbanladder.com/",
        }
        try:
            async with AsyncSession(impersonate="chrome124") as session:
                for slug in slug_candidates:
                    url = f"https://www.urbanladder.com/{slug}"
                    resp = await session.get(url, headers=headers, timeout=12)
                    self.check_bot_detection(resp.status_code, resp.text)
                    if resp.status_code == 200:
                        cand = self._extract_urban_ladder_app_data(resp.text, product_name, brand, barcode, url, catalog_price=catalog_price)
                        if not cand:
                            cand = self._extract_structured_data(resp.text, product_name, brand, barcode, url, catalog_price=catalog_price)
                        if not cand:
                            cand = self._extract_cards(resp.text, product_name, brand, barcode, url)
                        if cand:
                            cand["scrape_mode"] = "internal_api"
                            return cand
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.warning(f"[Urban Ladder] Tier 1 API error: {e}")

        return None

    def _extract_urban_ladder_app_data(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str, catalog_price: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """Extract products from window.APP_DATA in Urban Ladder SSR HTML."""
        try:
            idx = html_text.find("window.APP_DATA = ")
            if idx == -1:
                return None
            start = idx + len("window.APP_DATA = ")
            data, _ = json.JSONDecoder().raw_decode(html_text, start)

            items = (
                data.get("reduxData", {}).get("collection", {}).get("item", {}).get("items", [])
                or data.get("reduxData", {}).get("catalog", {}).get("products", {}).get("items", [])
                or data.get("reduxData", {}).get("catalog", {}).get("search_results", {}).get("items", [])
                or data.get("custom", {}).get("fpiEventproduct_list", {}).get("view", {}).get("result", {}).get("payload", {}).get("data", {}).get("items", [])
            )
            if not items:
                return None

            best_candidate = None
            best_score = 0.0

            for it in items:
                name = it.get("name")
                if not name:
                    continue
                score = self.compute_match_score(
                    name, target_name, brand, barcode,
                    catalog_price=catalog_price
                )
                if score < MATCH_THRESHOLD:
                    continue

                eff = it.get("price", {}).get("effective", {})
                p_val = eff.get("min") if isinstance(eff, dict) else eff
                if not p_val:
                    continue
                clean_p = re.sub(r"[^\d.]", "", str(p_val).replace(",", ""))
                try:
                    price = float(clean_p)
                except (ValueError, TypeError):
                    continue
                if price <= 0:
                    continue

                if catalog_price > 0 and (price < (catalog_price * 0.20) or price > (catalog_price * 5.0)):
                    continue

                marked = it.get("price", {}).get("marked", {})
                m_val = marked.get("min") if isinstance(marked, dict) else marked
                mrp = None
                if m_val:
                    try:
                        mrp_num = float(re.sub(r"[^\d.]", "", str(m_val).replace(",", "")))
                        if mrp_num >= price:
                            mrp = mrp_num
                    except (ValueError, TypeError):
                        pass

                slug = it.get("slug")
                prod_url = f"https://www.urbanladder.com/products/{slug}" if slug else search_url
                url_verified = bool(slug)

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "Urban Ladder",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(name),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "internal_api",
                        "data_source": "live_scrape",
                    }
            return best_candidate
        except Exception as e:
            logger.debug(f"[Urban Ladder] APP_DATA parse error: {e}")
            return None

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from Urban Ladder search results."""
        try:
            cand = self._extract_urban_ladder_app_data(html_text, target_name, brand, barcode, search_url)
            if cand:
                return cand
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = (
                soup.select("div[data-testid='plp-product-card']")
                or soup.select("div.xmdLL")
                or soup.select("li.product")
                or soup.select("div.productbox")
                or soup.select("div[class*='productbox']")
                or soup.select("li[class*='product']")
            )
            for card in cards:
                title_node = (
                    card.select_one("a[data-testid='plp-product-card-title']")
                    or card.select_one("span.name")
                    or card.select_one("span.product-title")
                    or card.select_one("div.product-title")
                    or card.select_one("h2.XxwSy")
                    or card.select_one("a.product-title-sofa")
                    or card.select_one("div[class*='title']")
                    or card.find("a", href=True)
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)
                brand_node = card.select_one("div.TsIP5, div[class*='brand'], span[class*='brand']")
                brand_text = brand_node.get_text(strip=True) if brand_node else "Urban Ladder"
                combined_title = f"{brand_text} {title}".strip()

                score = max(
                    self.compute_match_score(title, target_name, brand, barcode),
                    self.compute_match_score(combined_title, target_name, brand, barcode),
                )
                if score < MATCH_THRESHOLD:
                    continue

                price_node = (
                    card.select_one("div.UYQNp")
                    or card.select_one("div.price-number span")
                    or card.select_one("span.price")
                    or card.select_one("div.price-number")
                    or card.select_one("span[class*='price']")
                )
                if not price_node:
                    continue
                clean_p = re.sub(r"[^\d.]", "", price_node.get_text(strip=True).replace(",", ""))
                try:
                    price = float(clean_p)
                except ValueError:
                    continue
                if price <= 0:
                    continue

                mrp = None
                mrp_node = (
                    card.select_one("div.gc4ZJ")
                    or card.select_one("strike, span.strike, div[class*='original-price']")
                )
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                link_node = (
                    card.select_one("a[data-testid='plp-product-card-title']")
                    or card.select_one("a[href*='/product/']")
                    or card.select_one("a[href*='/products/']")
                    or card.select_one("a.product-img[href]")
                    or card.find("a", href=True)
                )
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"].split("?")[0]
                    if href.startswith("/"):
                        prod_url = f"https://www.urbanladder.com{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "Urban Ladder",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }
            return best_candidate
        except Exception as e:
            logger.debug(f"[Urban Ladder] DOM parse error: {e}")
            return None


class OneMgScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="1mg",
            search_url_template="https://www.1mg.com/search/all?name={query}",
            base_url="https://www.1mg.com",
        )

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str) -> Optional[Dict[str, Any]]:
        """1mg search extraction via curl_cffi: API gateways, preloaded state, and DOM fallback."""
        from urllib.parse import quote_plus
        from curl_cffi.requests import AsyncSession

        clean_query = self.clean_search_query(product_name, brand)
        if not clean_query:
            clean_query = product_name

        api_urls = [
            (
                f"https://www.1mg.com/pwa-dweb-api/api/v4/search/all?"
                f"q={quote_plus(clean_query)}&city=New%20Delhi&page_number=0&per_page=20&types=sku,allopathy"
            ),
            (
                f"https://www.1mg.com/pharmacy_api_gateway/v4/search/all?"
                f"q={quote_plus(clean_query)}&city=New%20Delhi&page_number=0&per_page=20&types=sku,allopathy"
            ),
        ]
        html_search_url = f"https://www.1mg.com/search/all?name={quote_plus(clean_query)}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": html_search_url,
        }

        try:
            async with AsyncSession(impersonate="chrome124") as session:
                # 1. Attempt JSON pharmacy search APIs
                for api_url in api_urls:
                    try:
                        resp = await session.get(api_url, headers=headers, timeout=10)
                        self.check_bot_detection(resp.status_code, resp.text)
                        if resp.status_code == 200:
                            cand = self._parse_json_payload(resp.json(), product_name, brand, barcode, html_search_url)
                            if cand:
                                cand["scrape_mode"] = "internal_api"
                                return cand
                    except (PlatformRateLimitError, BotDetectionEncountered) as bde:
                        raise bde
                    except Exception:
                        pass

                # 2. Fallback to HTML search page
                html_headers = dict(headers)
                html_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                resp_html = await session.get(html_search_url, headers=html_headers, timeout=12)
                self.check_bot_detection(resp_html.status_code, resp_html.text)
                if resp_html.status_code == 200:
                    # Check window.PRELOADED_STATE or window.__INITIAL_STATE__
                    state_match = re.search(
                        r"(?:window\.PRELOADED_STATE|window\.__INITIAL_STATE__)\s*=\s*(\{.*?\});",
                        resp_html.text
                    )
                    if state_match:
                        try:
                            state_data = json.loads(state_match.group(1))
                            cand = self._parse_json_payload(state_data, product_name, brand, barcode, html_search_url)
                            if cand:
                                cand["scrape_mode"] = "internal_api"
                                return cand
                        except Exception:
                            pass

                    # Structured data LD+JSON
                    cand = self._extract_structured_data(resp_html.text, product_name, brand, barcode, html_search_url)
                    if not cand:
                        cand = self._extract_cards(resp_html.text, product_name, brand, barcode, html_search_url)
                    if cand:
                        cand["scrape_mode"] = "internal_api"
                        return cand
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.warning(f"[1mg] Tier 1 API error: {e}")

        return None

    def _parse_json_payload(
        self, payload: Any, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """Extract product candidate from 1mg API or preloaded state."""
        if not isinstance(payload, dict):
            return None

        results = []
        d = payload.get("data")
        if isinstance(d, dict) and "search_results" in d:
            results = d["search_results"]
        elif "search_results" in payload:
            results = payload["search_results"]
        elif "searchReducer" in payload:
            sr = payload["searchReducer"].get("searchResults", {})
            if isinstance(sr, dict) and "search_results" in sr:
                results = sr["search_results"]

        best_candidate = None
        best_score = 0.0
        for item in results:
            if not isinstance(item, dict):
                continue
            title = item.get("name") or item.get("title")
            if not title:
                continue
            score = self.compute_match_score(title, target_name, brand, barcode)
            if score < MATCH_THRESHOLD:
                continue

            p_dict = item.get("prices") if isinstance(item.get("prices"), dict) else {}
            price_val = (
                p_dict.get("discounted_price")
                or item.get("discounted_price")
                or p_dict.get("price")
                or item.get("price")
            )
            if not price_val:
                continue
            clean_p = re.sub(r"[^\d.]", "", str(price_val).replace(",", ""))
            try:
                price = float(clean_p)
            except ValueError:
                continue
            if price <= 0:
                continue

            mrp_val = p_dict.get("mrp") or item.get("mrp")
            mrp = None
            if mrp_val:
                clean_m = re.sub(r"[^\d.]", "", str(mrp_val).replace(",", ""))
                try:
                    mrp_num = float(clean_m)
                    if mrp_num >= price:
                        mrp = mrp_num
                except ValueError:
                    pass

            url_path = item.get("url") or item.get("slug")
            prod_url = f"https://www.1mg.com{url_path}" if url_path and url_path.startswith("/") else (
                url_path if url_path and url_path.startswith("http") else search_url
            )
            url_verified = bool(url_path)

            if score > best_score:
                best_score = score
                best_candidate = {
                    "platform": "1mg",
                    "price": price,
                    "mrp": mrp,
                    "currency": "INR",
                    "in_stock": item.get("available", True),
                    "stock_status": "in_stock" if item.get("available", True) else "out_of_stock",
                    "product_url": prod_url,
                    "url_verified": url_verified,
                    "product_title": self.sanitize_output(title),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "match_score": score,
                    "unverified_match": False,
                    "scrape_mode": "internal_api",
                    "data_source": "live_scrape",
                }

        return best_candidate

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from 1mg search results with prefix wildcards."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = (
                soup.select("div[class*='style__product-box']")
                or soup.select("div[class*='style__product-card']")
                or soup.select("div[class*='cardContainer']")
                or soup.select("div[class*='product-card']")
            )
            for card in cards:
                title_node = (
                    card.select_one("div[class*='style__pro-title']")
                    or card.select_one("span[class*='style__pro-title']")
                    or card.select_one("div[class*='VerticalProductTile-module__header']")
                    or card.select_one("div[class*='pro-title']")
                    or card.select_one("div[class*='title']")
                    or card.find("a", href=True)
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)
                score = self.compute_match_score(title, target_name, brand, barcode)
                if score < MATCH_THRESHOLD:
                    continue

                price_node = (
                    card.select_one("div[class*='style__price-tag']")
                    or card.select_one("span.textPrimary.l5Medium")
                    or card.select_one("div[class*='style__price']")
                    or card.select_one("div[class*='price']")
                    or card.select_one("span[class*='price']")
                )
                if not price_node:
                    continue
                clean_p = re.sub(r"[^\d.]", "", price_node.get_text(strip=True).replace(",", ""))
                try:
                    price = float(clean_p)
                except ValueError:
                    continue
                if price <= 0:
                    continue

                mrp = None
                mrp_node = (
                    card.select_one("strike")
                    or card.select_one("span[class*='style__discount-price']")
                    or card.select_one("span[class*='discount-price']")
                )
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                link_node = (
                    card.select_one("a[href*='/drugs/']")
                    or card.select_one("a[href*='/otc/']")
                    or card.find("a", href=True)
                )
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"].split("?")[0]
                    if href.startswith("/"):
                        prod_url = f"https://www.1mg.com{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "1mg",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }
            return best_candidate
        except Exception as e:
            logger.debug(f"[1mg] DOM parse error: {e}")
            return None


class PharmEasyScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="PharmEasy",
            search_url_template="https://pharmeasy.in/search/all?name={query}",
            base_url="https://pharmeasy.in",
        )

    async def _tier1_internal_api(
        self, product_name: str, brand: str, barcode: str, catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        from urllib.parse import quote_plus
        from curl_cffi.requests import AsyncSession

        clean_query = self.clean_search_query(product_name, brand)
        search_url = f"https://pharmeasy.in/search/all?name={quote_plus(clean_query)}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://pharmeasy.in/",
        }

        try:
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(search_url, headers=headers, timeout=10)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200:
                    cand = self._extract_cards(resp.text, product_name, brand, barcode, search_url, catalog_price=catalog_price)
                    if cand:
                        cand["scrape_mode"] = "internal_api"
                        return cand
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.debug(f"[PharmEasy] Tier 1 API error: {e}")
        return None

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Extract product cards via __NEXT_DATA__ or DOM from PharmEasy search results."""
        import json
        best_candidate = None
        best_score = 0.0

        # 1. Parse __NEXT_DATA__ JSON script
        idx = html_text.find('id="__NEXT_DATA__"')
        if idx != -1:
            s_start = html_text.find(">", idx) + 1
            s_end = html_text.find("</script>", s_start)
            if s_start > 0 and s_end > s_start:
                try:
                    next_data = json.loads(html_text[s_start:s_end].strip())
                    products = (
                        next_data.get("props", {}).get("pageProps", {}).get("productList", []) or
                        next_data.get("props", {}).get("pageProps", {}).get("products", [])
                    )
                    for p in products:
                        title = p.get("name") or p.get("title") or ""
                        if not title:
                            continue
                        score = self.compute_match_score(title, target_name, brand, barcode)
                        if score < MATCH_THRESHOLD:
                            continue
                        price_raw = p.get("salePriceDecimal") or p.get("salePrice") or p.get("price") or p.get("mrpDecimal")
                        if not price_raw:
                            continue
                        try:
                            price = float(re.sub(r"[^\d.]", "", str(price_raw).replace(",", "")))
                        except (ValueError, TypeError):
                            continue
                        if price <= 0:
                            continue

                        mrp_raw = p.get("mrpDecimal") or p.get("mrp")
                        mrp = None
                        if mrp_raw:
                            try:
                                m_val = float(re.sub(r"[^\d.]", "", str(mrp_raw).replace(",", "")))
                                if m_val >= price:
                                    mrp = m_val
                            except (ValueError, TypeError):
                                pass

                        slug = p.get("slug")
                        prod_url = f"https://pharmeasy.in/online-medicine-order/{slug}" if slug else search_url

                        if score > best_score:
                            best_score = score
                            best_candidate = {
                                "platform": "PharmEasy",
                                "price": price,
                                "mrp": mrp,
                                "currency": "INR",
                                "in_stock": True,
                                "stock_status": "in_stock",
                                "product_url": prod_url,
                                "url_verified": bool(slug),
                                "product_title": self.sanitize_output(title),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "match_score": score,
                                "unverified_match": False,
                                "scrape_mode": "internal_api",
                                "data_source": "live_scrape",
                            }
                    if best_candidate:
                        return best_candidate
                except Exception as e:
                    logger.debug(f"[PharmEasy] Next data error: {e}")

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")

            cards = (
                soup.select("div.ProductCard_productCard__eE3wG")
                or soup.select("div[class*='ProductCard']")
                or soup.select("div[class*='productCard']")
                or soup.select("div[class*='product-card']")
            )
            for card in cards:
                title_node = (
                    card.select_one("h1[class*='title']")
                    or card.select_one("div[class*='title']")
                    or card.select_one("a[class*='ProductCard_productName']")
                    or card.select_one("h3")
                    or card.find("a", href=True)
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)
                score = self.compute_match_score(title, target_name, brand, barcode)
                if score < MATCH_THRESHOLD:
                    continue

                price_node = (
                    card.select_one("div.ProductCard_ourPrice__yDytt")
                    or card.select_one("div[class*='ourPrice']")
                    or card.select_one("span[class*='ourPrice']")
                    or card.select_one("span[class*='price']")
                )
                if not price_node:
                    continue
                clean_p = re.sub(r"[^\d.]", "", price_node.get_text(strip=True).replace(",", ""))
                try:
                    price = float(clean_p)
                except ValueError:
                    continue
                if price <= 0:
                    continue

                mrp = None
                mrp_node = card.select_one("span[class*='originalPrice'], span[class*='mrp']")
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                link_node = card.select_one("a[href]") or card.find("a", href=True)
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"].split("?")[0]
                    if href.startswith("/"):
                        prod_url = f"https://pharmeasy.in{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "PharmEasy",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }
            return best_candidate
        except Exception as e:
            logger.debug(f"[PharmEasy] DOM parse error: {e}")
            return None


class CaratLaneScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="CaratLane",
            search_url_template="https://www.caratlane.com/catalogsearch/result?q={query}",
            base_url="https://www.caratlane.com",
        )

    def _parse_preloaded_products(
        self, products: List[Dict[str, Any]], target_name: str, brand: str, barcode: str,
        search_url: str, catalog_price: float = 0.0
    ) -> Optional[Dict[str, Any]]:
        """Parses product list from CaratLane window.__PRELOADED_STATE__."""
        best_candidate = None
        best_rank = -1.0

        for p in products:
            if not isinstance(p, dict):
                continue
            title = p.get("name") or p.get("title") or p.get("productName")
            if not title:
                continue

            # Parse selling price (special_price takes precedence over price)
            price = 0.0
            sp = p.get("special_price")
            reg_p = p.get("price")
            if sp is not None:
                try:
                    price = float(sp)
                except (ValueError, TypeError):
                    pass
            if price <= 0.0 and reg_p is not None:
                try:
                    price = float(reg_p)
                except (ValueError, TypeError):
                    pass

            if price <= 0.0:
                # Fallback to formatted strings e.g. "₹78,995"
                for fp in [p.get("formatted_special_price"), p.get("formatted_price")]:
                    if fp:
                        clean = re.sub(r"[^\d.]", "", str(fp).replace(",", ""))
                        try:
                            val = float(clean)
                            if val > 0:
                                price = val
                                break
                        except ValueError:
                            pass

            if price <= 0.0:
                continue

            brand_text = "CaratLane"
            if isinstance(p.get("brand"), list) and p.get("brand"):
                brand_text = str(p.get("brand")[0])
            elif isinstance(p.get("brand"), str) and p.get("brand"):
                brand_text = p.get("brand")

            combined_title = f"{brand_text} {title}".strip()
            score = max(
                self.compute_match_score(
                    title, target_name, brand, barcode,
                    catalog_price=catalog_price, scraped_price=price
                ),
                self.compute_match_score(
                    combined_title, target_name, brand, barcode,
                    catalog_price=catalog_price, scraped_price=price
                ),
            )
            if score < MATCH_THRESHOLD:
                continue

            # Parse MRP
            mrp = None
            if reg_p is not None:
                try:
                    reg_val = float(reg_p)
                    if reg_val >= price:
                        mrp = reg_val
                except (ValueError, TypeError):
                    pass
            elif p.get("formatted_price"):
                clean_fp = re.sub(r"[^\d.]", "", str(p.get("formatted_price")).replace(",", ""))
                try:
                    reg_val = float(clean_fp)
                    if reg_val >= price:
                        mrp = reg_val
                except ValueError:
                    pass

            # Canonical product link
            rel_url = p.get("url") or p.get("slug")
            prod_url = search_url
            url_verified = False
            if rel_url:
                if str(rel_url).startswith("http"):
                    prod_url = str(rel_url)
                    url_verified = True
                elif str(rel_url).startswith("/"):
                    prod_url = f"https://www.caratlane.com{rel_url}"
                    url_verified = True

            diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0) if catalog_price > 0 else 0.0
            rank = score - (0.25 * diff_ratio)

            if rank > best_rank:
                best_rank = rank
                best_candidate = {
                    "platform": "CaratLane",
                    "price": price,
                    "mrp": mrp,
                    "currency": "INR",
                    "in_stock": True,
                    "stock_status": "in_stock",
                    "product_url": prod_url,
                    "url_verified": url_verified,
                    "product_title": self.sanitize_output(title),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "match_score": score,
                    "unverified_match": False,
                    "scrape_mode": "internal_api",
                    "data_source": "live_scrape",
                }

        return best_candidate

    async def _tier1_internal_api(
        self, product_name: str, brand: str, barcode: str, catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """CaratLane search extraction via curl_cffi: preloaded state, microdata, and DOM fallback."""
        from urllib.parse import quote, quote_plus
        from curl_cffi.requests import AsyncSession

        clean_query = self.clean_search_query(product_name, brand)
        if not clean_query:
            clean_query = product_name

        search_url = f"https://www.caratlane.com/catalogsearch/result?q={quote_plus(clean_query)}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.caratlane.com/",
        }

        try:
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(search_url, headers=headers, timeout=12)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200:
                    html_text = resp.text

                    # 1. Parse window.__PRELOADED_STATE__
                    if "window.__PRELOADED_STATE__" in html_text:
                        idx = html_text.find("window.__PRELOADED_STATE__ = ")
                        if idx != -1:
                            start = idx + len("window.__PRELOADED_STATE__ = ")
                            try:
                                decoder = json.JSONDecoder()
                                state, _ = decoder.raw_decode(html_text[start:])
                                products = state.get("listingPage", {}).get("listingData", {}).get("products", [])
                                if products:
                                    cand = self._parse_preloaded_products(
                                        products, product_name, brand, barcode, search_url, catalog_price
                                    )
                                    if cand:
                                        cand["scrape_mode"] = "internal_api"
                                        return cand
                            except Exception as pex:
                                logger.debug(f"[CaratLaneScraperAgent] preloaded state parse error: {pex}")

                    # 2. Check structured data (schema.org microdata / ld+json)
                    struct_cand = self._extract_structured_data(
                        html_text, product_name, brand, barcode, search_url, catalog_price=catalog_price
                    )
                    if struct_cand:
                        struct_cand["scrape_mode"] = "internal_api"
                        return struct_cand

                    # 3. Fallback to DOM card parsing
                    dom_cand = self._extract_cards(
                        html_text, product_name, brand, barcode, search_url, catalog_price=catalog_price
                    )
                    if dom_cand:
                        dom_cand["scrape_mode"] = "internal_api"
                        return dom_cand

                    # Retry once with first 3 core tokens if query is long (> 3 tokens)
                    tokens = clean_query.split()
                    if len(tokens) > 3:
                        relaxed_query = " ".join(tokens[:3])
                        relaxed_url = f"https://www.caratlane.com/catalogsearch/result?q={quote_plus(relaxed_query)}"
                        relaxed_resp = await session.get(relaxed_url, headers=headers, timeout=12)
                        if relaxed_resp.status_code == 200:
                            if "window.__PRELOADED_STATE__" in relaxed_resp.text:
                                r_idx = relaxed_resp.text.find("window.__PRELOADED_STATE__ = ")
                                if r_idx != -1:
                                    r_start = r_idx + len("window.__PRELOADED_STATE__ = ")
                                    try:
                                        r_state, _ = json.JSONDecoder().raw_decode(relaxed_resp.text[r_start:])
                                        r_prods = r_state.get("listingPage", {}).get("listingData", {}).get("products", [])
                                        if r_prods:
                                            cand = self._parse_preloaded_products(
                                                r_prods, product_name, brand, barcode, relaxed_url, catalog_price
                                            )
                                            if cand:
                                                cand["scrape_mode"] = "internal_api"
                                                return cand
                                    except Exception:
                                        pass
                            r_dom = self._extract_cards(
                                relaxed_resp.text, product_name, brand, barcode, relaxed_url, catalog_price=catalog_price
                            )
                            if r_dom:
                                r_dom["scrape_mode"] = "internal_api"
                                return r_dom
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.warning(f"[CaratLaneScraperAgent] _tier1_internal_api error: {e}")

        return None

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from CaratLane search results with microdata and CSS selector support."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_rank = -1.0

            # 1. First check schema.org/Product microdata containers
            items = soup.select("div[itemtype*='schema.org/Product'], [itemscope][itemtype*='Product']")
            for item in items:
                name_node = item.select_one("meta[itemprop='name']")
                price_node = item.select_one("meta[itemprop='price']")
                if not name_node or not price_node:
                    continue
                title = name_node.get("content", "").strip()
                if not title:
                    continue

                try:
                    price = float(price_node.get("content", 0.0))
                except (ValueError, TypeError):
                    continue
                if price <= 0:
                    continue

                combined_title = f"CaratLane {title}".strip()
                score = max(
                    self.compute_match_score(
                        title, target_name, brand, barcode,
                        catalog_price=catalog_price, scraped_price=price
                    ),
                    self.compute_match_score(
                        combined_title, target_name, brand, barcode,
                        catalog_price=catalog_price, scraped_price=price
                    ),
                )
                if score < MATCH_THRESHOLD:
                    continue

                mrp = None
                mrp_node = item.select_one("meta[itemprop='highPrice']")
                if mrp_node:
                    try:
                        m_val = float(mrp_node.get("content", 0.0))
                        if m_val >= price:
                            mrp = m_val
                    except (ValueError, TypeError):
                        pass

                link_node = item.select_one("link[itemprop='url']") or item.select_one("a[href]")
                prod_url = search_url
                url_verified = False
                if link_node:
                    href = link_node.get("href") or link_node.get("content")
                    if href:
                        clean_href = str(href).split("?")[0]
                        if clean_href.startswith("http"):
                            prod_url = clean_href
                            url_verified = True
                        elif clean_href.startswith("/"):
                            prod_url = f"https://www.caratlane.com{clean_href}"
                            url_verified = True

                diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0) if catalog_price > 0 else 0.0
                rank = score - (0.25 * diff_ratio)

                if rank > best_rank:
                    best_rank = rank
                    best_candidate = {
                        "platform": "CaratLane",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }

            if best_candidate:
                return best_candidate

            # 2. General DOM card elements
            cards = (
                soup.select("div[class*='productCard']")
                or soup.select("div[class*='ProductCard']")
                or soup.select("div[class*='product-card']")
                or soup.select("div[class*='cardContainer']")
                or soup.select("div.css-1447zhi")
                or soup.select("a[href*='/jewellery/'][href$='.html']")
            )

            for card in cards:
                title_node = (
                    card.select_one("p[class*='title']")
                    or card.select_one("div[class*='title']")
                    or card.select_one("h2")
                    or card.select_one("h3")
                    or card.select_one("div[class*='name']")
                    or card.find("a", href=True)
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)
                if not title:
                    continue

                price_node = (
                    card.select_one("span.price")
                    or card.select_one("span.offerPrice")
                    or card.select_one("p[class*='price']")
                    or card.select_one("div[class*='price']")
                    or card.select_one("span[class*='price']")
                )
                if not price_node:
                    continue
                clean_p = re.sub(r"[^\d.]", "", price_node.get_text(strip=True).replace(",", ""))
                try:
                    price = float(clean_p)
                except ValueError:
                    continue
                if price <= 0:
                    continue

                combined_title = f"CaratLane {title}".strip()
                score = max(
                    self.compute_match_score(
                        title, target_name, brand, barcode,
                        catalog_price=catalog_price, scraped_price=price
                    ),
                    self.compute_match_score(
                        combined_title, target_name, brand, barcode,
                        catalog_price=catalog_price, scraped_price=price
                    ),
                )
                if score < MATCH_THRESHOLD:
                    continue

                mrp = None
                mrp_node = card.select_one("span.strikePrice, span[class*='strike'], span[class*='mrp'], del, s")
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                link_node = card if card.name == "a" and card.get("href") else (card.select_one("a[href]") or card.find("a", href=True))
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"].split("?")[0]
                    if href.startswith("/"):
                        prod_url = f"https://www.caratlane.com{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0) if catalog_price > 0 else 0.0
                rank = score - (0.25 * diff_ratio)

                if rank > best_rank:
                    best_rank = rank
                    best_candidate = {
                        "platform": "CaratLane",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }

            return best_candidate
        except Exception as e:
            logger.debug(f"[CaratLane] DOM parse error: {e}")
            return None


class TanishqScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Tanishq",
            search_url_template="https://www.tanishq.co.in/shop?q={query}",
            base_url="https://www.tanishq.co.in",
        )

    async def _tier1_internal_api(
        self, product_name: str, brand: str, barcode: str, catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Tanishq search extraction via curl_cffi: structured data, SFCC data-gtmdata, and DOM tiles."""
        from urllib.parse import quote_plus
        from curl_cffi.requests import AsyncSession

        search_brand = "" if brand and brand.lower() in ("tanishq", "mia", "mia by tanishq") else brand
        clean_query = self.clean_search_query(product_name, search_brand) or product_name

        search_url = f"https://www.tanishq.co.in/shop?q={quote_plus(clean_query)}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.tanishq.co.in/",
        }

        try:
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(search_url, headers=headers, timeout=12)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200:
                    html_text = resp.text

                    # 1. Check structured data (application/ld+json)
                    struct_cand = self._extract_structured_data(
                        html_text, product_name, search_brand, barcode, search_url, catalog_price=catalog_price
                    )
                    if struct_cand:
                        struct_cand["scrape_mode"] = "internal_api"
                        return struct_cand

                    # 2. Extract SFCC tiles and data-gtmdata
                    dom_cand = self._extract_cards(
                        html_text, product_name, brand, barcode, search_url, catalog_price=catalog_price
                    )
                    if dom_cand:
                        dom_cand["scrape_mode"] = "internal_api"
                        return dom_cand

                    # 3. Retry once with first 3 core tokens if query is long (> 3 tokens)
                    tokens = clean_query.split()
                    if len(tokens) > 3:
                        relaxed_query = " ".join(tokens[:3])
                        relaxed_url = f"https://www.tanishq.co.in/shop?q={quote_plus(relaxed_query)}"
                        relaxed_resp = await session.get(relaxed_url, headers=headers, timeout=12)
                        if relaxed_resp.status_code == 200:
                            r_struct = self._extract_structured_data(
                                relaxed_resp.text, product_name, search_brand, barcode, relaxed_url, catalog_price=catalog_price
                            )
                            if r_struct:
                                r_struct["scrape_mode"] = "internal_api"
                                return r_struct

                            r_dom = self._extract_cards(
                                relaxed_resp.text, product_name, brand, barcode, relaxed_url, catalog_price=catalog_price
                            )
                            if r_dom:
                                r_dom["scrape_mode"] = "internal_api"
                                return r_dom
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.warning(f"[TanishqScraperAgent] _tier1_internal_api error: {e}")

        return None

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from Tanishq SFCC product tiles with data-gtmdata JSON and selector support."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_rank = -1.0

            cards = (
                soup.select("div.product-tile")
                or soup.select("div[class*='product-tile']")
                or soup.select("div.product-card")
                or soup.select("div[class*='product-card']")
            )

            for card in cards:
                title = None
                price = 0.0
                in_stock = True
                stock_status = "in_stock"
                brand_text = "Tanishq"

                # 1. Parse data-gtmdata JSON attribute
                gtm_raw = card.get("data-gtmdata")
                if gtm_raw:
                    try:
                        gtm = json.loads(gtm_raw)
                        title = gtm.get("item_name")
                        if gtm.get("price") is not None:
                            price = float(gtm.get("price"))
                        if gtm.get("stockStatus") and "out" in str(gtm.get("stockStatus")).lower():
                            in_stock = False
                            stock_status = "out_of_stock"
                        if gtm.get("item_brand"):
                            brand_text = str(gtm.get("item_brand"))
                    except Exception:
                        pass

                # 2. Fallback to DOM elements if missing from data-gtmdata
                if not title:
                    title_node = (
                        card.select_one("a.product-tile__name")
                        or card.select_one("div.product-name")
                        or card.select_one("div[class*='title']")
                        or card.select_one("a[class*='name']")
                        or card.select_one("h2")
                        or card.select_one("h3")
                        or card.find("a", href=True)
                    )
                    if title_node:
                        title = title_node.get_text(strip=True)

                if not title:
                    continue

                if price <= 0.0:
                    price_node = (
                        card.select_one("span.sales span.value")
                        or card.select_one("span.sales")
                        or card.select_one("div.sales")
                        or card.select_one("span.product-price")
                        or card.select_one("span[class*='sales']")
                        or card.select_one("span[class*='price']")
                    )
                    if price_node:
                        val_attr = price_node.get("content") or price_node.get("value")
                        if val_attr:
                            try:
                                price = float(val_attr)
                            except ValueError:
                                pass
                        if price <= 0.0:
                            clean_p = re.sub(r"[^\d.]", "", price_node.get_text(strip=True).replace(",", ""))
                            try:
                                price = float(clean_p)
                            except ValueError:
                                pass

                if price <= 0.0:
                    continue

                combined_tanishq = f"Tanishq {title}".strip()
                combined_brand = f"{brand_text} {title}".strip()
                score = max(
                    self.compute_match_score(
                        title, target_name, brand, barcode,
                        catalog_price=catalog_price, scraped_price=price
                    ),
                    self.compute_match_score(
                        combined_tanishq, target_name, brand, barcode,
                        catalog_price=catalog_price, scraped_price=price
                    ),
                    self.compute_match_score(
                        combined_brand, target_name, brand, barcode,
                        catalog_price=catalog_price, scraped_price=price
                    ),
                )
                if score < MATCH_THRESHOLD:
                    continue

                # Parse MRP
                mrp = None
                mrp_node = card.select_one("span.strike-through, span[class*='mrp'], span[class*='strike'], del, s")
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                # Canonical link
                link_node = (
                    card.select_one("a.product-tile__name")
                    or card.select_one("a[href*='.html']")
                    or card.select_one("a[href]")
                    or card.find("a", href=True)
                )
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"].split("?")[0]
                    if href.startswith("/"):
                        prod_url = f"https://www.tanishq.co.in{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0) if catalog_price > 0 else 0.0
                rank = score - (0.25 * diff_ratio)

                if rank > best_rank:
                    best_rank = rank
                    best_candidate = {
                        "platform": "Tanishq",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": in_stock,
                        "stock_status": stock_status,
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }

            return best_candidate
        except Exception as e:
            logger.debug(f"[Tanishq] DOM parse error: {e}")
            return None


class CromaScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Croma",
            search_url_template="https://www.croma.com/searchB?q={query}%3Arelevance&text={query}",
            base_url="https://www.croma.com",
        )

    def _extract_croma_from_json(
        self, data: dict, product_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(data, dict):
            return None
        products = data.get("products", [])
        if not isinstance(products, list) or not products:
            return None

        best_candidate = None
        best_rank = -1.0

        for p in products:
            if not isinstance(p, dict):
                continue
            title = p.get("name", "")
            if not title:
                continue

            price = float(p.get("price", {}).get("value", 0) or 0)
            if price <= 0:
                continue

            score = self.compute_match_score(
                title, product_name, brand, barcode,
                catalog_price=catalog_price, scraped_price=price
            )
            if score < MATCH_THRESHOLD:
                continue

            url_path = p.get("url", "")
            mrp_val = float(p.get("mrp", {}).get("value", 0) or 0)
            prod_url = search_url
            url_verified = False
            if url_path:
                clean_path = url_path.split("?")[0]
                if clean_path.startswith("/"):
                    prod_url = f"https://www.croma.com{clean_path}"
                    url_verified = True
                elif clean_path.startswith("http"):
                    prod_url = clean_path
                    url_verified = True

            in_stock = bool(p.get("stockFlag")) or p.get("stock", {}).get("stockLevelStatus") != "outOfStock"

            if catalog_price > 0:
                diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                rank = score - (0.25 * diff_ratio)
            else:
                rank = score

            if rank > best_rank:
                best_rank = rank
                best_candidate = {
                    "platform": "Croma",
                    "price": price,
                    "mrp": mrp_val if (mrp_val and mrp_val >= price) else None,
                    "currency": "INR",
                    "in_stock": bool(in_stock),
                    "stock_status": "in_stock" if in_stock else "out_of_stock",
                    "product_url": prod_url,
                    "url_verified": url_verified,
                    "product_title": self.sanitize_output(title),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "match_score": score,
                    "unverified_match": False,
                    "scrape_mode": "internal_api",
                    "data_source": "live_scrape",
                }

        return best_candidate

    async def _tier1_internal_api(
        self, product_name: str, brand: str, barcode: str
    ) -> Optional[Dict[str, Any]]:
        """Query Croma's search API via curl_cffi Chrome 124 for structured product data."""
        query = self.clean_search_query(product_name, brand)
        api_url = (
            f"https://api.croma.com/searchservices/v1/search"
            f"?currentPage=0&query={quote_plus(query)}%3Arelevance&fields=FULL&channel=WEB&channelCode=400049"
        )
        headers = {
            "Origin": "https://www.croma.com",
            "Referer": "https://www.croma.com/",
            "Accept": "application/json",
            "csc-channel": "WEB",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(api_url, headers=headers, timeout=12)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200:
                    data = resp.json()
                    search_url = self.build_search_url(query)
                    candidate = self._extract_croma_from_json(
                        data, product_name, brand, barcode, search_url
                    )
                    if candidate:
                        candidate["scrape_mode"] = "internal_api"
                        return candidate
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            logger.warning(f"[{self.platform_name}] tier1 anti-bot encountered: {bde}")
            raise bde
        except Exception as e:
            logger.debug(f"[Croma] API search error: {e}")
        return None

    def _extract_croma_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from Croma search result HTML."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = (
                soup.select("li.product-item")
                or soup.select("div.product-card")
                or soup.select("div[class*='product']")
            )

            for card in cards:
                title_node = (
                    card.select_one("h3.product-title a, a.product__list--name, h3 a")
                    or card.find("a", href=True)
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)
                score = self.compute_match_score(title, target_name, brand, barcode)
                if score < MATCH_THRESHOLD:
                    continue

                price_node = card.select_one(
                    "span.amount, span[data-testid='new-price'], "
                    "span.pdpPriceMrp, div.new-price, span.price"
                )
                if not price_node:
                    continue
                clean_p = re.sub(
                    r"[^\d.]", "",
                    price_node.get_text(strip=True).replace(",", ""),
                )
                try:
                    price = float(clean_p)
                except ValueError:
                    continue
                if price <= 0:
                    continue

                mrp = None
                mrp_node = card.select_one(
                    "span.old-price, span[data-testid='old-price'], span.pdpPriceList"
                )
                if mrp_node:
                    clean_m = re.sub(
                        r"[^\d.]", "",
                        mrp_node.get_text(strip=True).replace(",", ""),
                    )
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                link = title_node.get("href") or ""
                prod_url = search_url
                url_verified = False
                if link.startswith("/"):
                    prod_url = f"https://www.croma.com{link.split('?')[0]}"
                    url_verified = True
                elif link.startswith("http"):
                    prod_url = link.split("?")[0]
                    url_verified = True

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "Croma",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "playwright_stealth",
                        "data_source": "live_scrape",
                    }

            return best_candidate
        except Exception as e:
            logger.debug(f"[Croma] DOM parse error: {e}")
            return None

    _extract_cards = _extract_croma_cards

    async def _tier2_mobile_headers(
        self, task_id: str, product_id: str, organization_id: str,
        product_name: str, brand: str, barcode: str, proxy: Optional[str] = None,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """HTTP fetch of Croma search page with card extraction."""
        import aiohttp
        query = self.clean_search_query(product_name, brand)
        search_url = self.build_search_url(query)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
        }
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=12)
            ) as session:
                async with session.get(
                    search_url, headers=headers, proxy=proxy
                ) as resp:
                    html_text = await resp.text()
                    self.check_bot_detection(resp.status, html_text)
                    candidate = self._extract_croma_cards(
                        html_text, product_name, brand, barcode, search_url, catalog_price=catalog_price
                    )
                    if candidate:
                        candidate["scrape_mode"] = "mobile_headers"
                        return candidate
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            logger.info(
                f"[Croma] tier2 HTTP bot challenge; falling back to Playwright: {bde}"
            )
            return None
        except Exception as ex:
            logger.warning(f"[Croma] HTTP request error: {ex}")
            return None
        return None

    async def _tier3_playwright(
        self, task_id: str, product_id: str, organization_id: str,
        product_name: str, brand: str, barcode: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Playwright stealth render with response interception for Croma search results."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return None

        query = self.clean_search_query(product_name, brand)
        search_url = self.build_search_url(query)
        try:
            validate_outbound_url(search_url)
        except ValueError:
            return None

        sem = _get_playwright_semaphore()
        intercepted_json = []

        async def _handle_response(response):
            if "searchservices/v1/search" in response.url and response.status == 200:
                try:
                    ct = response.headers.get("content-type", "")
                    if "application/json" in ct or "text/json" in ct:
                        body = await response.json()
                        intercepted_json.append(body)
                except Exception:
                    pass

        html_text = ""
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
                    ],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    ),
                    locale="en-IN",
                    viewport={"width": 1366, "height": 768},
                )
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.chrome = { runtime: {} };
                """)
                page = await context.new_page()
                page.on("response", _handle_response)
                await page.route(
                    re.compile(r"\.(png|jpg|jpeg|gif|webp|ico)(\?.*)?$"),
                    lambda r: r.abort(),
                )
                await page.goto(search_url, timeout=25000, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)
                html_text = await page.content()
                self.check_bot_detection(200, html_text)
            except (PlatformRateLimitError, BotDetectionEncountered) as bde:
                logger.warning(f"[Croma] tier3 anti-bot detected: {bde}")
                raise bde
            except Exception as ex:
                logger.warning(f"[Croma] tier3 playwright failed: {ex}")
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

        # First, evaluate any intercepted searchservices/v1/search JSON
        for data in intercepted_json:
            cand = self._extract_croma_from_json(
                data, product_name, brand, barcode, search_url, catalog_price=catalog_price
            )
            if cand:
                cand["scrape_mode"] = "playwright_stealth"
                return cand

        # Fallback to DOM card extraction
        if html_text:
            candidate = self._extract_croma_cards(
                html_text, product_name, brand, barcode, search_url, catalog_price=catalog_price
            )
            if candidate:
                candidate["scrape_mode"] = "playwright_stealth"
                return candidate

        return None


class MeeshoScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Meesho",
            search_url_template="https://www.meesho.com/search?q={query}",
            base_url="https://www.meesho.com",
        )

    async def _tier1_internal_api(
        self, product_name: str, brand: str, barcode: str, catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Query Meesho search API for structured catalog JSON."""
        from urllib.parse import quote_plus
        from curl_cffi.requests import AsyncSession

        query = self.clean_search_query(product_name, brand)
        api_url = "https://www.meesho.com/api/v1/products/search"
        headers = {
            "Origin": "https://www.meesho.com",
            "Referer": f"https://www.meesho.com/search?q={quote_plus(query)}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        payload = {
            "query": query,
            "type": "text_search",
            "page": 1,
            "offset": 0,
            "limit": 20,
        }
        try:
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.post(api_url, json=payload, headers=headers, timeout=12)
                self.check_bot_detection(resp.status_code, resp.text)
                if resp.status_code == 200:
                    data = resp.json()
                    catalogs = data.get("catalogs", [])
                    best_candidate = None
                    best_rank = -1.0
                    for c in catalogs:
                        name = c.get("hero_product_name") or c.get("name") or ""
                        title = f"{brand} {name}".strip() if brand and brand.lower() not in name.lower() else name
                        try:
                            price = float(c.get("min_catalog_price") or c.get("min_product_price") or 0.0)
                        except (ValueError, TypeError):
                            continue
                        if price <= 0:
                            continue

                        try:
                            mrp = float(c.get("mrp") or 0.0) or None
                        except (ValueError, TypeError):
                            mrp = None

                        if catalog_price > 0 and (price < (catalog_price * 0.20) or price > (catalog_price * 5.0)):
                            continue

                        score = self.compute_match_score(
                            title, product_name, brand, barcode,
                            catalog_price=catalog_price, scraped_price=price
                        )
                        if score < MATCH_THRESHOLD:
                            continue

                        slug = c.get("slug")
                        pid = c.get("product_id") or c.get("id")
                        if slug and pid:
                            prod_url = f"https://www.meesho.com/{slug}/p/{pid}"
                            url_verified = True
                        elif pid:
                            prod_url = f"https://www.meesho.com/s/p/{pid}"
                            url_verified = True
                        else:
                            prod_url = self.base_url
                            url_verified = False

                        if catalog_price > 0:
                            diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                            rank = score - (0.25 * diff_ratio)
                        else:
                            rank = score

                        if rank > best_rank:
                            best_rank = rank
                            best_candidate = {
                                "platform": "Meesho",
                                "price": price,
                                "mrp": mrp if mrp and mrp >= price else None,
                                "currency": "INR",
                                "in_stock": True,
                                "stock_status": "in_stock",
                                "product_url": prod_url,
                                "url_verified": url_verified,
                                "product_title": self.sanitize_output(title),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "match_score": score,
                                "unverified_match": False,
                                "scrape_mode": "internal_api",
                                "data_source": "live_scrape",
                            }
                    if best_candidate:
                        return best_candidate

                    # Fallback query if brand caused 0 matches (e.g. unbranded fashion)
                    clean_no_brand = self.clean_search_query(product_name, "")
                    if clean_no_brand and clean_no_brand != query:
                        payload_retry = {
                            "query": clean_no_brand,
                            "type": "text_search",
                            "page": 1,
                            "offset": 0,
                            "limit": 30,
                        }
                        resp_retry = await session.post(api_url, json=payload_retry, headers=headers, timeout=12)
                        self.check_bot_detection(resp_retry.status_code, resp_retry.text)
                        if resp_retry.status_code == 200:
                            data_retry = resp_retry.json()
                            catalogs_retry = data_retry.get("catalogs", [])
                            for c in catalogs_retry:
                                name = c.get("hero_product_name") or c.get("name") or ""
                                title = f"{brand} {name}".strip() if brand and brand.lower() not in name.lower() else name
                                try:
                                    price = float(c.get("min_catalog_price") or c.get("min_product_price") or 0.0)
                                except (ValueError, TypeError):
                                    continue
                                if price <= 0:
                                    continue
                                if catalog_price > 0 and (price < (catalog_price * 0.20) or price > (catalog_price * 5.0)):
                                    continue
                                score = self.compute_match_score(
                                    title, product_name, brand, barcode,
                                    catalog_price=catalog_price, scraped_price=price
                                )
                                if score < MATCH_THRESHOLD:
                                    continue
                                slug = c.get("slug")
                                pid = c.get("product_id") or c.get("id")
                                prod_url = f"https://www.meesho.com/{slug}/p/{pid}" if slug and pid else self.base_url
                                return {
                                    "platform": "Meesho",
                                    "price": price,
                                    "mrp": None,
                                    "currency": "INR",
                                    "in_stock": True,
                                    "stock_status": "in_stock",
                                    "product_url": prod_url,
                                    "url_verified": bool(slug and pid),
                                    "product_title": self.sanitize_output(title),
                                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                                    "match_score": score,
                                    "unverified_match": False,
                                    "scrape_mode": "internal_api",
                                    "data_source": "live_scrape",
                                }
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.debug(f"[Meesho] API search error: {e}")
        return None

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Parse Meesho product cards via __NEXT_DATA__ or DOM."""
        import json
        best_candidate = None
        best_rank = -1.0

        # 1. Parse __NEXT_DATA__ hydration JSON if present
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).strip())
                initial_state = data.get("props", {}).get("pageProps", {}).get("initialState", {})
                products = (
                    initial_state.get("searchListing", {}).get("listing", {}).get("products")
                    or data.get("props", {}).get("pageProps", {}).get("catalogs")
                    or initial_state.get("plpListing", {}).get("listing", {}).get("products")
                    or []
                )
                for item in products:
                    name = item.get("hero_product_name") or item.get("name") or ""
                    title = f"{brand} {name}".strip() if brand and brand.lower() not in name.lower() else name
                    try:
                        price = float(item.get("min_catalog_price") or item.get("min_product_price") or item.get("price") or 0.0)
                    except (ValueError, TypeError):
                        continue
                    if price <= 0:
                        continue
                    if catalog_price > 0 and (price < (catalog_price * 0.20) or price > (catalog_price * 5.0)):
                        continue

                    try:
                        mrp = float(item.get("mrp") or 0.0) or None
                    except (ValueError, TypeError):
                        mrp = None

                    score = self.compute_match_score(
                        title, target_name, brand, barcode,
                        catalog_price=catalog_price, scraped_price=price
                    )
                    if score < MATCH_THRESHOLD:
                        continue

                    slug = item.get("slug")
                    pid = item.get("product_id") or item.get("id")
                    if slug and pid:
                        prod_url = f"https://www.meesho.com/{slug}/p/{pid}"
                        url_verified = True
                    elif pid:
                        prod_url = f"https://www.meesho.com/s/p/{pid}"
                        url_verified = True
                    else:
                        prod_url = search_url
                        url_verified = False

                    if catalog_price > 0:
                        diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                        rank = score - (0.25 * diff_ratio)
                    else:
                        rank = score

                    if rank > best_rank:
                        best_rank = rank
                        best_candidate = {
                            "platform": "Meesho",
                            "price": price,
                            "mrp": mrp if mrp and mrp >= price else None,
                            "currency": "INR",
                            "in_stock": True,
                            "stock_status": "in_stock",
                            "product_url": prod_url,
                            "url_verified": url_verified,
                            "product_title": self.sanitize_output(title),
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                            "match_score": score,
                            "unverified_match": False,
                            "scrape_mode": "mobile_headers",
                            "data_source": "live_scrape",
                        }
                if best_candidate:
                    return best_candidate
            except Exception as jex:
                logger.debug(f"[Meesho] __NEXT_DATA__ parse error: {jex}")

        # 2. Fall back to DOM card selectors
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")

            cards = (
                soup.select("div[class*='ProductCard']")
                or soup.select("div[class*='Card__StyledCard']")
                or soup.select("a[href*='/p/']")
            )

            for card in cards:
                title_node = (
                    card.select_one("p[class*='Title']")
                    or card.select_one("span[class*='Title']")
                    or card.select_one("p[class*='CardTitle']")
                    or card.find(["p", "span", "h5"])
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)

                price_node = (
                    card.select_one("h5[class*='Price']")
                    or card.select_one("p[class*='Price']")
                    or card.select_one("span[class*='Price']")
                    or card.select_one("h5")
                )
                if not price_node:
                    continue
                clean_p = re.sub(r"[^\d.]", "", price_node.get_text(strip=True).replace(",", ""))
                try:
                    price = float(clean_p)
                except ValueError:
                    continue
                if price <= 0:
                    continue

                score = self.compute_match_score(
                    title, target_name, brand, barcode,
                    catalog_price=catalog_price, scraped_price=price
                )
                if score < MATCH_THRESHOLD:
                    continue

                mrp = None
                mrp_node = card.select_one("p[class*='Mrp'], span[class*='Mrp'], p[class*='DiscountedPrice']")
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                link_node = card if card.name == "a" and card.get("href") else (card.select_one("a[href*='/p/']") or card.find("a", href=True))
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"].split("?")[0]
                    if href.startswith("/"):
                        prod_url = f"https://www.meesho.com{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if catalog_price > 0:
                    diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                    rank = score - (0.25 * diff_ratio)
                else:
                    rank = score

                if rank > best_rank:
                    best_rank = rank
                    best_candidate = {
                        "platform": "Meesho",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }
            return best_candidate
        except Exception as e:
            logger.debug(f"[Meesho] DOM parse error: {e}")
            return None


class BlinkitScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Blinkit",
            search_url_template="https://blinkit.com/s/?q={query}",
            base_url="https://blinkit.com",
        )
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "app_client": "consumer_web",
            "lat": "28.6139",
            "lon": "77.2090",
            "app_version": "1010101010",
        }

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str) -> Optional[Dict[str, Any]]:
        """Blinkit two-step session handshake and layout/search JSON parser."""
        import uuid
        from datetime import datetime, timezone
        from urllib.parse import quote, quote_plus
        from curl_cffi.requests import AsyncSession

        clean_query = " ".join(re.sub(r"[^a-zA-Z0-9\s]", " ", f"{brand} {product_name}").split())
        if not clean_query:
            clean_query = product_name

        headers = dict(self.headers)
        headers["session_uuid"] = str(uuid.uuid4())
        headers["device_id"] = uuid.uuid4().hex[:16]
        headers["auth_key"] = "c761ec3633c22afad934fb17a66385c1c06c5472b4898b866b7306186d0bb477"

        try:
            async with AsyncSession(impersonate="chrome124") as session:
                # Step 1: Lightweight GET to bootstrap cookies & session tokens
                try:
                    boot_resp = await session.get("https://blinkit.com", headers={"User-Agent": headers["User-Agent"]}, timeout=8)
                    self.check_bot_detection(boot_resp.status_code, boot_resp.text)
                except (PlatformRateLimitError, BotDetectionEncountered) as bde:
                    raise bde
                except Exception:
                    pass

                # Step 2: Query layout search
                encoded_query = quote(clean_query)
                layout_url = f"https://blinkit.com/v1/layout/search?q={encoded_query}&search_type=type_to_search"
                resp = await session.post(layout_url, headers=headers, json={}, timeout=10)
                self.check_bot_detection(resp.status_code, resp.text)

                if resp.status_code == 200:
                    data = resp.json()
                    snippets = data.get("response", {}).get("snippets", [])
                    best_candidate = None
                    best_score = 0.0

                    for snip in snippets:
                        d = snip.get("data", {})
                        title = d.get("name", {}).get("text") or d.get("display_name", {}).get("text") or d.get("name")
                        if not title:
                            continue
                        score = self.compute_match_score(title, product_name, brand, barcode)
                        if score < MATCH_THRESHOLD:
                            continue

                        price_raw = d.get("normal_price", {}).get("text") or d.get("price") or 0
                        clean_p = re.sub(r"[^\d.]", "", str(price_raw).replace(",", ""))
                        try:
                            price = float(clean_p)
                            if price > 5000:
                                price = price / 100.0
                        except ValueError:
                            continue
                        if price <= 0:
                            continue

                        mrp_raw = d.get("mrp", {}).get("text") or d.get("mrp")
                        mrp = None
                        if mrp_raw:
                            clean_m = re.sub(r"[^\d.]", "", str(mrp_raw).replace(",", ""))
                            try:
                                mrp_val = float(clean_m)
                                if mrp_val >= price:
                                    mrp = mrp_val
                            except ValueError:
                                pass

                        pid = d.get("product_id") or d.get("identity", {}).get("id") or "prod"
                        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
                        in_stock = not d.get("is_sold_out", False)

                        if score > best_score:
                            best_score = score
                            best_candidate = {
                                "platform": "Blinkit",
                                "price": price,
                                "mrp": mrp,
                                "currency": "INR",
                                "in_stock": in_stock,
                                "stock_status": "in_stock" if in_stock else "out_of_stock",
                                "product_url": f"https://blinkit.com/prn/{slug}/prid/{pid}",
                                "url_verified": True,
                                "product_title": self.sanitize_output(title),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "match_score": score,
                                "unverified_match": False,
                                "scrape_mode": "internal_api",
                                "data_source": "live_scrape",
                            }

                    if best_candidate:
                        return best_candidate

                # Fallback search URL if layout didn't yield candidate
                v1_url = f"https://blinkit.com/v1/search?q={quote_plus(clean_query)}&lat=28.6139&lon=77.2090"
                resp_v1 = await session.get(v1_url, headers=headers, timeout=10)
                self.check_bot_detection(resp_v1.status_code, resp_v1.text)
                if resp_v1.status_code == 200:
                    v1_data = resp_v1.json()
                    products = v1_data.get("products") or v1_data.get("items") or []
                    for item in products:
                        title = item.get("name") or item.get("title") or product_name
                        score = self.compute_match_score(title, product_name, brand, barcode)
                        if score >= MATCH_THRESHOLD:
                            price = float(item.get("price") or item.get("discounted_price") or 0.0)
                            if price > 5000:
                                price = price / 100.0
                            if price > 0:
                                pid = item.get("product_id") or item.get("id") or "prod"
                                slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
                                in_stock = bool(item.get("inventory", 1) > 0)
                                return {
                                    "platform": "Blinkit",
                                    "price": price,
                                    "mrp": float(item.get("mrp") or 0) or None,
                                    "currency": "INR",
                                    "in_stock": in_stock,
                                    "stock_status": "in_stock" if in_stock else "out_of_stock",
                                    "product_url": f"https://blinkit.com/prn/{slug}/prid/{pid}",
                                    "url_verified": True,
                                    "product_title": self.sanitize_output(title),
                                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                                    "match_score": score,
                                    "unverified_match": False,
                                    "scrape_mode": "internal_api",
                                    "data_source": "live_scrape",
                                }
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.warning(f"[Blinkit] API error: {e}")

        return None

    async def _tier3_playwright(
        self, task_id: str, product_id: str, organization_id: str,
        product_name: str, brand: str, barcode: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return None

        clean_query = " ".join((f"{brand} {product_name}").split())
        search_url = f"https://blinkit.com/s/?q={quote_plus(clean_query)}"
        try:
            validate_outbound_url(search_url)
        except ValueError:
            return None

        sem = _get_playwright_semaphore()
        candidate = None
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
                    ],
                )
                context = await browser.new_context(
                    user_agent=self.headers["User-Agent"],
                    locale="en-IN",
                    viewport={"width": 1366, "height": 768},
                    timezone_id="Asia/Kolkata",
                    geolocation={"latitude": 28.6139, "longitude": 77.2090},
                    permissions=["geolocation"],
                )
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                """)
                page = await context.new_page()
                api_data = None

                async def on_response(response):
                    nonlocal api_data
                    if "layout/search" in response.url and not api_data:
                        try:
                            api_data = await response.json()
                        except Exception:
                            pass

                page.on("response", on_response)
                await page.goto(search_url, timeout=25000, wait_until="domcontentloaded")
                await page.wait_for_timeout(4000)

                if api_data:
                    snippets = api_data.get("response", {}).get("snippets", [])
                    best_score = 0.0
                    for snip in snippets:
                        d = snip.get("data", {})
                        title = d.get("name", {}).get("text") or d.get("display_name", {}).get("text") or d.get("name")
                        if not title:
                            continue
                        score = self.compute_match_score(title, product_name, brand, barcode)
                        if score < MATCH_THRESHOLD:
                            continue
                        price_raw = d.get("normal_price", {}).get("text") or d.get("price") or 0
                        clean_p = re.sub(r"[^\d.]", "", str(price_raw).replace(",", ""))
                        try:
                            price = float(clean_p)
                            if price > 5000:
                                price = price / 100.0
                        except ValueError:
                            continue
                        if price <= 0:
                            continue

                        mrp_raw = d.get("mrp", {}).get("text") or d.get("mrp")
                        mrp = None
                        if mrp_raw:
                            clean_m = re.sub(r"[^\d.]", "", str(mrp_raw).replace(",", ""))
                            try:
                                mrp_val = float(clean_m)
                                if mrp_val >= price:
                                    mrp = mrp_val
                            except ValueError:
                                pass

                        pid = d.get("product_id") or d.get("identity", {}).get("id") or "prod"
                        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
                        in_stock = not d.get("is_sold_out", False)

                        if score > best_score:
                            best_score = score
                            candidate = {
                                "platform": "Blinkit",
                                "price": price,
                                "mrp": mrp,
                                "currency": "INR",
                                "in_stock": in_stock,
                                "stock_status": "in_stock" if in_stock else "out_of_stock",
                                "product_url": f"https://blinkit.com/prn/{slug}/prid/{pid}",
                                "url_verified": True,
                                "product_title": self.sanitize_output(title),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "match_score": score,
                                "unverified_match": False,
                                "scrape_mode": "playwright",
                                "data_source": "live_scrape",
                            }
            except Exception as e:
                logger.warning(f"[Blinkit] Playwright tier3 failed: {e}")
            finally:
                if browser:
                    try: await browser.close()
                    except Exception: pass
                if pw_instance:
                    try: await pw_instance.stop()
                    except Exception: pass

        return candidate


class ScoobooScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Scooboo",
            search_url_template="https://scooboo.in/search?q={query}",
            base_url="https://scooboo.in",
        )

    @staticmethod
    def _parse_shopify_price(val: Any) -> float:
        if val is None:
            return 0.0
        val_str = str(val).strip()
        clean = re.sub(r"[^\d.]", "", val_str.replace(",", ""))
        try:
            num = float(clean)
            if "." not in val_str and num >= 10000:
                num = num / 100.0
            return round(num, 2)
        except ValueError:
            return 0.0

    async def _tier1_internal_api(
        self, product_name: str, brand: str, barcode: str, catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Scooboo Shopify suggest JSON search API with canonical product page variant extraction."""
        from datetime import datetime, timezone
        from urllib.parse import quote_plus
        from curl_cffi.requests import AsyncSession

        clean_query = self.clean_search_query(product_name, brand)
        headers = {
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        }

        try:
            async with AsyncSession(impersonate="chrome124") as session:
                async def _fetch_suggest(q: str):
                    api_url = f"https://scooboo.in/search/suggest.json?q={quote_plus(q)}&resources[type]=product&resources[limit]=10"
                    resp = await session.get(api_url, headers=headers, timeout=10)
                    self.check_bot_detection(resp.status_code, resp.text)
                    if resp.status_code != 200:
                        return []
                    data = resp.json()
                    return data.get("resources", {}).get("results", {}).get("products", [])

                products = await _fetch_suggest(clean_query)

                # Query relaxation: if products empty and len > 3 tokens, retry once with 3 tokens
                tokens = clean_query.split()
                if not products and len(tokens) > 3:
                    relaxed_query = " ".join(tokens[:3])
                    products = await _fetch_suggest(relaxed_query)

                if not products:
                    return None

                target_lower = product_name.lower()
                is_refill_target = "refill" in target_lower

                best_candidate_prod = None
                best_score = 0.0

                for prod in products:
                    title = prod.get("title") or ""
                    title_lower = title.lower()

                    # Exclude items with "Refill" in title unless target product asks for refill
                    if "refill" in title_lower and not is_refill_target:
                        continue

                    # Strict keyword matching if query has airpress / pen
                    if ("airpress" in target_lower or "air press" in target_lower) and not ("airpress" in title_lower or "air press" in title_lower):
                        continue
                    if "pen" in target_lower and "pen" not in title_lower:
                        continue

                    score = self.compute_match_score(
                        title, product_name, brand, barcode, catalog_price=catalog_price
                    )
                    if score < MATCH_THRESHOLD:
                        continue

                    if score > best_score:
                        best_score = score
                        best_candidate_prod = prod

                if not best_candidate_prod:
                    return None

                handle = best_candidate_prod.get("handle")
                if not handle:
                    return None

                # Fetch canonical product page JSON to get exact primary variant price
                canonical_url = f"https://scooboo.in/products/{handle}"
                detail_url = f"https://scooboo.in/products/{handle}.json"
                price = 0.0
                mrp = None
                available = bool(best_candidate_prod.get("available", True))

                try:
                    detail_resp = await session.get(detail_url, headers=headers, timeout=10)
                    if detail_resp.status_code == 200:
                        detail_data = detail_resp.json()
                        variants = detail_data.get("product", {}).get("variants", [])
                        if variants:
                            # Primary variant
                            v0 = variants[0]
                            price = self._parse_shopify_price(v0.get("price"))
                            mrp_raw = v0.get("compare_at_price")
                            if mrp_raw:
                                mrp_parsed = self._parse_shopify_price(mrp_raw)
                                if mrp_parsed >= price:
                                    mrp = mrp_parsed
                            if v0.get("available") is not None:
                                available = bool(v0.get("available"))
                except Exception as dex:
                    logger.debug(f"[Scooboo] Product detail fetch error for {handle}: {dex}")

                if price <= 0:
                    # Fallback to suggest price if detail fetch failed
                    price = self._parse_shopify_price(best_candidate_prod.get("price"))
                    mrp_raw = best_candidate_prod.get("compare_at_price_max") or best_candidate_prod.get("compare_at_price")
                    mrp = self._parse_shopify_price(mrp_raw) if mrp_raw else None
                    if best_candidate_prod.get("available") is not None:
                        available = bool(best_candidate_prod.get("available"))

                if price <= 0:
                    return None

                return {
                    "platform": "Scooboo",
                    "price": price,
                    "mrp": mrp,
                    "currency": "INR",
                    "in_stock": available,
                    "stock_status": "in_stock" if available else "out_of_stock",
                    "product_url": canonical_url,
                    "url_verified": True,
                    "product_title": self.sanitize_output(best_candidate_prod.get("title") or product_name),
                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                    "match_score": best_score,
                    "unverified_match": False,
                    "scrape_mode": "internal_api",
                    "data_source": "live_scrape",
                }
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.warning(f"[Scooboo] API error: {e}")

        return None

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """DOM parsing for https://scooboo.in/search?q={query}."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_rank = -1.0

            cards = (
                soup.select(".product-card")
                or soup.select(".grid-product")
                or soup.select("div[class*='product-item']")
                or soup.select("div[class*='product-card']")
                or soup.select("a[href*='/products/']")
            )

            target_lower = target_name.lower()
            is_refill_target = "refill" in target_lower

            for card in cards:
                title_node = (
                    card.select_one(".product-card__title a, .grid-product__title, a.product-item__title")
                    or card.select_one("a[href*='/products/']")
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)
                if not title:
                    continue

                title_lower = title.lower()
                if "refill" in title_lower and not is_refill_target:
                    continue

                # Parse selling price
                price = 0.0
                price_nodes = card.select(
                    ".f-price-item--sale, .price-item--sale, .f-price__sale .f-price-item, "
                    ".f-price-item, .price-item--regular, .grid-product__price, span.price"
                )
                for pn in price_nodes:
                    clean = re.sub(r"(?i)\b(?:rs\.?|inr)\b|[\u20b9₹]", "", pn.get_text(strip=True)).replace(",", "")
                    match = re.search(r"(\d+(?:\.\d+)?)", clean)
                    if match:
                        try:
                            p_val = float(match.group(1))
                            if p_val > 0:
                                price = p_val
                                break
                        except ValueError:
                            pass

                if price <= 0:
                    continue

                score = self.compute_match_score(
                    title, target_name, brand, barcode,
                    catalog_price=catalog_price, scraped_price=price
                )
                if score < MATCH_THRESHOLD:
                    continue

                # Parse MRP
                mrp = None
                mrp_nodes = card.select(
                    ".f-price-item--regular s, .price-item--regular s, s, "
                    ".f-price__sale .f-price-item--regular, .grid-product__price--original"
                )
                for mn in mrp_nodes:
                    clean_m = re.sub(r"(?i)\b(?:rs\.?|inr)\b|[\u20b9₹]", "", mn.get_text(strip=True)).replace(",", "")
                    match = re.search(r"(\d+(?:\.\d+)?)", clean_m)
                    if match:
                        try:
                            m_val = float(match.group(1))
                            if m_val >= price:
                                mrp = m_val
                                break
                        except ValueError:
                            pass

                # Canonical link
                link_node = card.select_one("a[href*='/products/']")
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"]
                    clean_href = href.split("?")[0]
                    if clean_href.startswith("/"):
                        prod_url = f"https://scooboo.in{clean_href}"
                        url_verified = True
                    elif clean_href.startswith("http"):
                        prod_url = clean_href
                        url_verified = True

                if catalog_price > 0:
                    diff_ratio = min(abs(price - catalog_price) / catalog_price, 1.0)
                    rank = score - (0.25 * diff_ratio)
                else:
                    rank = score

                if rank > best_rank:
                    best_rank = rank
                    best_candidate = {
                        "platform": "Scooboo",
                        "price": price,
                        "mrp": mrp,
                        "currency": "INR",
                        "in_stock": True,
                        "stock_status": "in_stock",
                        "product_url": prod_url,
                        "url_verified": url_verified,
                        "product_title": self.sanitize_output(title),
                        "scraped_at": datetime.now(timezone.utc).isoformat(),
                        "match_score": score,
                        "unverified_match": False,
                        "scrape_mode": "mobile_headers",
                        "data_source": "live_scrape",
                    }

            return best_candidate
        except Exception as e:
            logger.debug(f"[ScoobooScraperAgent] parsing error: {e}")
            return None

    async def _tier3_playwright(self, *args, **kwargs):
        """Shopify endpoints execute via standard HTTP; skip Playwright."""
        return None


PLATFORM_SCRAPERS: Dict[str, BaseScraperAgent] = {
    "Amazon.in": AmazonScraperAgent(),
    "Flipkart": FlipkartScraperAgent(),
    "Croma": CromaScraperAgent(),
    "Myntra": MyntraScraperAgent(),
    "Ajio": AjioScraperAgent(),
    "Meesho": MeeshoScraperAgent(),
    "Blinkit": BlinkitScraperAgent(),
    "Nykaa": NykaaScraperAgent(),
    "Purplle": PurplleScraperAgent(),
    "BigBasket": BigBasketScraperAgent(),
    "JioMart": JioMartScraperAgent(),
    "Scooboo": ScoobooScraperAgent(),
    "Pepperfry": PepperfryScraperAgent(),
    "Urban Ladder": UrbanLadderScraperAgent(),
    "1mg": OneMgScraperAgent(),
    "PharmEasy": PharmEasyScraperAgent(),
    "CaratLane": CaratLaneScraperAgent(),
    "Tanishq": TanishqScraperAgent(),
}

# Alias for registry discovery across test runners and tools
SCRAPER_REGISTRY: Dict[str, BaseScraperAgent] = PLATFORM_SCRAPERS

PLATFORM_ALIASES: Dict[str, str] = {
    "amazon": "Amazon.in",
    "amazon.in": "Amazon.in",
    "flipkart": "Flipkart",
    "croma": "Croma",
    "myntra": "Myntra",
    "ajio": "Ajio",
    "meesho": "Meesho",
    "blinkit": "Blinkit",
    "nykaa": "Nykaa",
    "purplle": "Purplle",
    "bigbasket": "BigBasket",
    "jiomart": "JioMart",
    "scooboo": "Scooboo",
    "pepperfry": "Pepperfry",
    "urban ladder": "Urban Ladder",
    "urbanladder": "Urban Ladder",
    "1mg": "1mg",
    "tata 1mg": "1mg",
    "tata1mg": "1mg",
    "pharmeasy": "PharmEasy",
    "caratlane": "CaratLane",
    "tanishq": "Tanishq",
}


class UnknownPlatformError(ValueError):
    """Raised when an unrecognized or unsupported platform is requested."""
    pass


def get_scraper_for_platform(platform_name: str) -> BaseScraperAgent:
    """
    Returns the scraper instance for a given platform name.

    Raises:
        UnknownPlatformError: If platform_name is unknown or unsupported. Never silently
                              falls back to another platform to prevent data corruption.
    """
    if not platform_name or not isinstance(platform_name, str):
        raise UnknownPlatformError("Platform name must be a non-empty string.")

    cleaned_name = platform_name.strip()

    # Exact match in registry
    if cleaned_name in PLATFORM_SCRAPERS:
        return PLATFORM_SCRAPERS[cleaned_name]

    # Normalized alias match (case-insensitive, whitespace-insensitive)
    normalized = cleaned_name.lower().replace("_", " ").replace("-", " ")
    if normalized in PLATFORM_ALIASES:
        canonical = PLATFORM_ALIASES[normalized]
        return PLATFORM_SCRAPERS[canonical]

    # Unknown platform: Raise explicit UnknownPlatformError to avoid silent cross-platform pollution
    valid_platforms = list(sorted(PLATFORM_SCRAPERS.keys()))
    raise UnknownPlatformError(
        f"Unsupported platform: '{platform_name}' is not a registered scraper platform. "
        f"Valid platforms: {valid_platforms}"
    )

