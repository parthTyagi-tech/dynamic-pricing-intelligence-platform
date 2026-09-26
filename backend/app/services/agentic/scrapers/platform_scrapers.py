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

                recipe_node = item.select_one('[data-cy="title-recipe"], .s-title-instructions-style')
                headers = [h.get_text(separator=' ', strip=True) for h in (recipe_node.find_all(["h2", "h3"]) if recipe_node else item.find_all(["h2", "h3"])) if h.get_text(strip=True)]
                if len(headers) >= 2 and len(headers[0]) < 25:
                    title = " ".join(headers)
                elif recipe_node and recipe_node.select_one("a.a-link-normal.s-line-clamp-2, a.a-link-normal.s-line-clamp-4"):
                    title = recipe_node.select_one("a.a-link-normal.s-line-clamp-2, a.a-link-normal.s-line-clamp-4").get_text(separator=' ', strip=True)
                elif headers:
                    title = headers[0]
                else:
                    title_node = item.find("h2")
                    if not title_node:
                        continue
                    title = title_node.get_text(separator=' ', strip=True)
                title_lower = title.lower()

                # Exclude refills if catalog query is a single unit pen
                if "refill" in title_lower and not is_refill_target:
                    continue

                # Strict Price Selector Scoping:
                # Specifically target primary selling price inside price instructions
                # Exclude bank offer text, EMI starting amounts, coupon badges, etc.
                price_container = (
                    item.select_one(".s-price-instructions-style .a-price:not(.a-text-price) .a-offscreen")
                    or item.select_one(".s-price-instructions-style .a-price .a-offscreen")
                    or item.select_one(".a-price:not(.a-text-price) .a-offscreen")
                    or item.select_one(".a-price .a-offscreen")
                )
                if not price_container:
                    continue

                p_text = price_container.get_text(strip=True)
                clean_p = re.sub(r"[^\d.]", "", p_text.replace(",", ""))
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

                # Live Product URL
                prod_url = search_url
                url_verified = False
                link_node = (
                    item.select_one("a.a-link-normal.s-no-outline[href]")
                    or title_node.find("a", href=True)
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
            logger.debug(f"[AmazonScraperAgent] parsing error: {e}")
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

        # Memory-safe Playwright lifecycle: explicit try/finally with pw.stop()
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

    def _extract_flipkart_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_rank = -1.0

            # Support all Flipkart container layouts (List, Grid, and Modern 2025/2026 classes)
            cards = (
                soup.select("div[data-id]")
                or soup.select("div.tUxRFH")
                or soup.select("div.slAVV4")
                or soup.select("div._4ddWXP")
                or soup.select("div.cPHDOP")
                or soup.select("div._1AtVbE div._13oc-S")
            )

            for card in cards:
                title_node = (
                    card.select_one(
                        "div.RG5Slk, div.KzDlHZ, a.wjcEIp, a.s1Q9rs, a.pIpigb, "
                        "div._4rR01T, a.VJA3rP, a[title]"
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

                # Support all Flipkart price classes
                price_node = card.select_one(
                    "div.Nx9bqj, div.hZ3P6w, div._30jeq3, "
                    "div.col-5-12 ._30jeq3, div[class*='price']"
                )
                if not price_node:
                    match = re.search(
                        r"(?:\u20b9|Rs\.?)\s*([\d,]+(?:\.\d{2})?)",
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

                # Rank by score and proximity to catalog_price if catalog_price > 0
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
        """Tier 1: Fast mobile browser search via curl_cffi TLS impersonation."""
        query = f"{brand} {product_name}".strip()
        search_url = self.build_search_url(query)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
        }
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(search_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    candidate = self._extract_flipkart_cards(resp.text, product_name, brand, barcode, search_url)
                    if candidate:
                        candidate["scrape_mode"] = "curl_cffi_mobile"
                        return candidate
        except Exception as e:
            logger.debug(f"[Flipkart] tier1 curl_cffi mobile search failed: {e}")
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

    async def _tier2_mobile_headers(
        self, task_id: str, product_id: str, organization_id: str,
        product_name: str, brand: str, barcode: str, proxy: Optional[str] = None,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """Use curl_cffi for TLS/JA3 and window.__myx JSON extraction with gateway fallback."""
        import json
        clean_name = product_name
        if brand and brand.lower() in clean_name.lower():
            words = clean_name.split()
            if words[0].lower() == brand.lower():
                clean_name = " ".join(words[1:])
        query_text = f"{brand} {clean_name}".strip() if brand else clean_name
        slug = re.sub(r"[^a-z0-9]+", "-", query_text.lower()).strip("-")
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
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(search_url, headers=headers, timeout=12)
                if resp.status_code == 200:
                    self.check_bot_detection(resp.status_code, resp.text)
                    # 1. Parse window.__myx embedded hydration JSON
                    idx = resp.text.find("window.__myx = ")
                    if idx != -1:
                        raw = resp.text[idx + len("window.__myx = "):]
                        end = raw.find("</script>")
                        clean_json = raw[:end].strip().rstrip(";")
                        try:
                            data = json.loads(clean_json)
                            products = data.get("searchData", {}).get("results", {}).get("products", [])
                            best_candidate = None
                            best_score = 0.0
                            for p in products:
                                title = p.get("productName") or f"{p.get('brand')} {p.get('additionalInfo')}" or p.get("product") or ""
                                price = float(p.get("price", 0))
                                mrp = float(p.get("mrp", 0))
                                score = self.compute_match_score(title, product_name, brand, barcode)
                                if score >= MATCH_THRESHOLD and price > 0:
                                    if score > best_score:
                                        best_score = score
                                        landing_url = p.get("landingPageUrl") or ""
                                        best_candidate = {
                                            "platform": self.platform_name,
                                            "price": price,
                                            "mrp": mrp if mrp >= price else None,
                                            "currency": "INR",
                                            "in_stock": True,
                                            "product_url": f"https://www.myntra.com/{landing_url.lstrip('/')}",
                                            "url_verified": True,
                                            "product_title": self.sanitize_output(title),
                                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                                            "match_score": score,
                                            "unverified_match": False,
                                            "scrape_mode": "curl_cffi_tls",
                                            "data_source": "live_scrape",
                                        }
                            if best_candidate:
                                return best_candidate
                        except Exception as jex:
                            logger.debug(f"[Myntra] window.__myx JSON parse error: {jex}")

                # 2. Gateway API search fallback
                gw_url = f"https://www.myntra.com/gateway/v2/search/{quote_plus(query_text)}?rows=20&o=0"
                try:
                    gw_resp = await session.get(gw_url, timeout=8)
                    if gw_resp.status_code == 200:
                        gw_data = gw_resp.json()
                        gw_products = gw_data.get("products", [])
                        for p in gw_products:
                            title = p.get("productName") or f"{p.get('brand')} {p.get('additionalInfo')}" or ""
                            price = float(p.get("price", 0))
                            mrp = float(p.get("mrp", 0))
                            score = self.compute_match_score(title, product_name, brand, barcode)
                            if score >= MATCH_THRESHOLD and price > 0:
                                return {
                                    "platform": self.platform_name,
                                    "price": price,
                                    "mrp": mrp if mrp >= price else None,
                                    "currency": "INR",
                                    "in_stock": True,
                                    "product_url": f"https://www.myntra.com/{p.get('landingPageUrl', '').lstrip('/')}",
                                    "url_verified": True,
                                    "product_title": self.sanitize_output(title),
                                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                                    "match_score": score,
                                    "unverified_match": False,
                                    "scrape_mode": "curl_cffi_gateway",
                                    "data_source": "live_scrape",
                                }
                except Exception:
                    pass
        except ImportError:
            logger.info("[Myntra] curl_cffi not installed; falling back to aiohttp.")
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.warning(f"[Myntra] curl_cffi request failed: {e}")

        # Fall back to base aiohttp tier2
        return await super()._tier2_mobile_headers(
            task_id, product_id, organization_id, product_name, brand, barcode, proxy, catalog_price=catalog_price
        )

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str,
        catalog_price: float = 0.0, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from Myntra search result HTML."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = soup.select("li.product-base") or soup.select("div.product-base") or soup.select("div[class*='product-base']")
            for card in cards:
                title_node = card.select_one("h4.product-product") or card.select_one("h3.product-brand") or card.select_one("div.product-brand")
                if not title_node:
                    continue
                brand_node = card.select_one("h3.product-brand")
                title = title_node.get_text(strip=True)
                if brand_node and brand_node != title_node:
                    title = f"{brand_node.get_text(strip=True)} {title}"

                score = self.compute_match_score(title, target_name, brand, barcode)
                if score < MATCH_THRESHOLD:
                    continue

                price_node = card.select_one("span.product-discountedPrice") or card.select_one("span.product-price") or card.select_one("div.product-price")
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
                mrp_node = card.select_one("span.product-strike")
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
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

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "Myntra",
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
                        "scrape_mode": "playwright_stealth",
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

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str) -> Optional[Dict[str, Any]]:
        """Query Ajio search API for structured product JSON."""
        query = self.clean_search_query(product_name, brand)
        api_url = f"https://www.ajio.com/api/search?text={quote_plus(query)}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(api_url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    products = data.get("products", [])
                    best_candidate = None
                    best_score = 0.0
                    for p in products:
                        title = p.get("name", "")
                        b = p.get("fnlColorVariantData", {}).get("brandName", "") or brand
                        if b and b.lower() not in title.lower():
                            title = f"{b} {title}"
                        score = self.compute_match_score(title, product_name, brand, barcode)
                        if score < MATCH_THRESHOLD:
                            continue
                        price_dict = p.get("price", {})
                        price = float(price_dict.get("value", 0.0) if isinstance(price_dict, dict) else (p.get("price") or 0.0))
                        if price <= 0:
                            continue
                        was_price_dict = p.get("wasPriceData", {})
                        mrp = float(was_price_dict.get("value", 0.0) if isinstance(was_price_dict, dict) else 0.0) or None
                        url_path = p.get("url", "")
                        if score > best_score:
                            best_score = score
                            best_candidate = {
                                "platform": "Ajio",
                                "price": price,
                                "mrp": mrp if mrp and mrp >= price else None,
                                "currency": "INR",
                                "in_stock": True,
                                "product_url": f"https://www.ajio.com{url_path}" if url_path.startswith("/") else url_path or self.base_url,
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
        except Exception as e:
            logger.debug(f"[Ajio] API search error: {e}")
        return None

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from Ajio search result grid."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = soup.select("div.item") or soup.select("div[class*='item']") or soup.select("div.preview")
            for card in cards:
                title_node = card.select_one("div.name") or card.select_one("div.nameCls") or card.select_one("div[class*='name']")
                brand_node = card.select_one("div.brand") or card.select_one("div[class*='brand']")
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)
                if brand_node:
                    b_text = brand_node.get_text(strip=True)
                    if b_text.lower() not in title.lower():
                        title = f"{b_text} {title}"

                score = self.compute_match_score(title, target_name, brand, barcode)
                if score < MATCH_THRESHOLD:
                    continue

                price_node = (
                    card.select_one("span.price")
                    or card.select_one("span.fnl-plp-price")
                    or card.select_one("div.price")
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
                mrp_node = card.select_one("span.orginal-price") or card.select_one("span.fnl-original-price")
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
                        prod_url = f"https://www.ajio.com{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "Ajio",
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
            logger.debug(f"[Ajio] DOM parse error: {e}")
            return None


class NykaaScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Nykaa",
            search_url_template="https://www.nykaa.com/search/result/?q={query}",
            base_url="https://www.nykaa.com",
        )

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """Parse Nykaa product cards."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = (
                soup.select("div.productWrapper")
                or soup.select("div[data-test-id='product-card']")
                or soup.select("div[class*='productCard']")
                or soup.select("div[class*='product-wrapper']")
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
                score = self.compute_match_score(title, target_name, brand, barcode)
                if score < MATCH_THRESHOLD:
                    continue

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

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "Nykaa",
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
            logger.debug(f"[Nykaa] DOM parse error: {e}")
            return None


class PurplleScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Purplle",
            search_url_template="https://www.purplle.com/search?q={query}",
            base_url="https://www.purplle.com",
        )

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from Purplle search results."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = (
                soup.select("div.product-card")
                or soup.select("div.item")
                or soup.select("div[class*='product-card']")
            )
            for card in cards:
                title_node = (
                    card.select_one("p.title")
                    or card.select_one("a.title")
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
                    card.select_one("span.price")
                    or card.select_one("span.actual-price")
                    or card.select_one("div.price")
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
                mrp_node = card.select_one("span.mrp, span.old-price, span[class*='mrp']")
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
                        prod_url = f"https://www.purplle.com{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "Purplle",
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

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str):
        """BigBasket search endpoint."""
        import aiohttp
        from datetime import datetime, timezone
        from urllib.parse import quote_plus

        query = quote_plus(f"{brand} {product_name}".strip())
        api_url = f"https://www.bigbasket.com/product/get-products/?slug={query}&page=1"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                async with session.get(api_url, headers=self.headers) as resp:
                    self.check_bot_detection(resp.status, "")
                    if resp.status == 200:
                        data = await resp.json()
                        tabs = data.get("tab", {}).get("product_info", {}).get("products", [])
                        best_candidate = None
                        best_score = 0.0
                        for p in tabs:
                            title = p.get("p_desc") or product_name
                            score = self.compute_match_score(title, product_name, brand, barcode)
                            if score < MATCH_THRESHOLD:
                                continue
                            try:
                                price = float(p.get("sp") or 0.0)
                            except (ValueError, TypeError):
                                continue
                            if price <= 0:
                                continue
                            mrp_raw = p.get("mrp")
                            mrp = float(mrp_raw) if mrp_raw and float(mrp_raw) >= price else None
                            p_url = f"https://www.bigbasket.com/pd/{p.get('p_id')}" if p.get("p_id") else f"https://www.bigbasket.com/ps/?q={query}"
                            if score > best_score:
                                best_score = score
                                best_candidate = {
                                    "platform": "BigBasket",
                                    "price": price,
                                    "mrp": mrp,
                                    "currency": "INR",
                                    "in_stock": True,
                                    "product_url": p_url,
                                    "url_verified": bool(p.get("p_id")),
                                    "product_title": self.sanitize_output(title),
                                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                                    "match_score": score,
                                    "unverified_match": False,
                                    "scrape_mode": "internal_api",
                                    "data_source": "live_scrape",
                                }
                        return best_candidate
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.warning(f"[BigBasket] API error: {e}")
        return None

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from BigBasket search result page."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
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

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from Pepperfry search results."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = (
                soup.select("div.clipCard")
                or soup.select("div.product-card")
                or soup.select("div[class*='clipCard']")
            )
            for card in cards:
                title_node = (
                    card.select_one("h2.clipCard__title")
                    or card.select_one("a.clipCard__title")
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
                    card.select_one("span.clipCard__price--bold")
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
                mrp_node = card.select_one("span.clipCard__mrp, span[class*='mrp']")
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

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from Urban Ladder search results."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = (
                soup.select("li.product")
                or soup.select("div.productbox")
                or soup.select("div[class*='productbox']")
                or soup.select("li[class*='product']")
            )
            for card in cards:
                title_node = (
                    card.select_one("span.product-title")
                    or card.select_one("div.product-title")
                    or card.select_one("a.product-title-sofa")
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
                    card.select_one("div.price-number span")
                    or card.select_one("span.price")
                    or card.select_one("div.price-number")
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
                mrp_node = card.select_one("strike, span.strike, div[class*='original-price']")
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                link_node = (
                    card.select_one("a[href*='/products/']")
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

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from 1mg search results."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = (
                soup.select("div.style__product-box___p2raQ")
                or soup.select("div[class*='style__product-card']")
                or soup.select("div[class*='product-card']")
                or soup.select("div[class*='style__product-box']")
            )
            for card in cards:
                title_node = (
                    card.select_one("div.style__pro-title___2QwJy")
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
                    card.select_one("div.style__price-tag___KzOkY")
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
                mrp_node = card.select_one("span.style__discount-price___25Bya, span[class*='discount-price']")
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

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from PharmEasy search results."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

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
            search_url_template="https://www.caratlane.com/search/{query}",
            base_url="https://www.caratlane.com",
        )

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from CaratLane search results."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = (
                soup.select("div.productCard")
                or soup.select("div[class*='ProductCard']")
                or soup.select("div[class*='product-card']")
            )
            for card in cards:
                title_node = (
                    card.select_one("p[class*='title']")
                    or card.select_one("div[class*='title']")
                    or card.select_one("h2")
                    or card.find("a", href=True)
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)
                score = self.compute_match_score(title, target_name, brand, barcode)
                if score < MATCH_THRESHOLD:
                    continue

                price_node = (
                    card.select_one("span.price")
                    or card.select_one("span.offerPrice")
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
                mrp_node = card.select_one("span.strikePrice, span[class*='strike'], span[class*='mrp']")
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
                        prod_url = f"https://www.caratlane.com{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "CaratLane",
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
            logger.debug(f"[CaratLane] DOM parse error: {e}")
            return None


class TanishqScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Tanishq",
            search_url_template="https://www.tanishq.co.in/shop?q={query}",
            base_url="https://www.tanishq.co.in",
        )

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """DOM extraction from Tanishq search results."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = (
                soup.select("div.product-tile")
                or soup.select("div.product-card")
                or soup.select("div[class*='product-tile']")
            )
            for card in cards:
                title_node = (
                    card.select_one("a.product-tile__name")
                    or card.select_one("div.product-name")
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
                    card.select_one("span.sales span.value")
                    or card.select_one("span.product-price")
                    or card.select_one("span[class*='sales']")
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
                mrp_node = card.select_one("span.strike-through, span[class*='mrp']")
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
                        prod_url = f"https://www.tanishq.co.in{href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href
                        url_verified = True

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "Tanishq",
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
            logger.debug(f"[Tanishq] DOM parse error: {e}")
            return None


class CromaScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Croma",
            search_url_template="https://www.croma.com/searchB?q={query}%3Arelevance&text={query}",
            base_url="https://www.croma.com",
        )

    async def _tier1_internal_api(
        self, product_name: str, brand: str, barcode: str
    ) -> Optional[Dict[str, Any]]:
        """Query Croma's search API for structured product data."""
        import aiohttp

        query = self.clean_search_query(product_name, brand)
        api_url = (
            f"https://api.croma.com/searchservices/v1/search"
            f"?currentPage=0&query={quote_plus(query)}&fields=FULL"
        )
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=8)
            ) as session:
                async with session.get(api_url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        products = data.get("products", [])
                        for p in products:
                            title = p.get("name", "")
                            score = self.compute_match_score(
                                title, product_name, brand, barcode
                            )
                            if score >= MATCH_THRESHOLD:
                                price = float(
                                    p.get("price", {}).get("value", 0) or 0
                                )
                                if price > 0:
                                    url_path = p.get("url", "")
                                    mrp_val = float(
                                        p.get("mrp", {}).get("value", 0) or 0
                                    )
                                    return {
                                        "platform": "Croma",
                                        "price": price,
                                        "mrp": mrp_val if mrp_val >= price else None,
                                        "currency": "INR",
                                        "in_stock": p.get("stock", {}).get(
                                            "stockLevelStatus"
                                        ) != "outOfStock",
                                        "product_url": (
                                            f"https://www.croma.com{url_path}"
                                            if url_path.startswith("/")
                                            else url_path or self.base_url
                                        ),
                                        "url_verified": bool(url_path),
                                        "product_title": self.sanitize_output(title),
                                        "scraped_at": datetime.now(
                                            timezone.utc
                                        ).isoformat(),
                                        "match_score": score,
                                        "unverified_match": False,
                                        "scrape_mode": "internal_api",
                                        "data_source": "live_scrape",
                                    }
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
        """Playwright stealth render of Croma search results page."""
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

    def _extract_cards(
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        """Parse Meesho product cards."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

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
                score = self.compute_match_score(title, target_name, brand, barcode)
                if score < MATCH_THRESHOLD:
                    continue

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

                if score > best_score:
                    best_score = score
                    best_candidate = {
                        "platform": "Meesho",
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
            logger.debug(f"[Meesho] DOM parse error: {e}")
            return None


class BlinkitScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Blinkit",
            search_url_template="https://blinkit.com/s/?q={query}",
            base_url="https://blinkit.com",
        )

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str) -> Optional[Dict[str, Any]]:
        """Blinkit two-step session handshake and layout/search JSON parser."""
        import uuid
        from datetime import datetime, timezone
        from urllib.parse import quote, quote_plus
        from curl_cffi.requests import AsyncSession

        clean_query = " ".join(re.sub(r"[^a-zA-Z0-9\s]", " ", f"{brand} {product_name}").split())
        if not clean_query:
            clean_query = product_name

        session_id = str(uuid.uuid4())
        device_id = uuid.uuid4().hex[:16]
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "app_client": "consumer_web",
            "lat": "12.9716",
            "lon": "77.5946",
            "session_uuid": session_id,
            "device_id": device_id,
            "auth_key": "c761ec3633c22afad934fb17a66385c1c06c5472b4898b866b7306186d0bb477",
            "app_version": "1010101010",
        }

        try:
            async with AsyncSession(impersonate="chrome124") as session:
                # Step 1: Lightweight GET to bootstrap cookies & session tokens
                try:
                    await session.get("https://blinkit.com", headers={"User-Agent": headers["User-Agent"]}, timeout=8)
                except Exception:
                    pass

                # Step 2: Query layout search
                encoded_query = quote(clean_query)
                layout_url = f"https://blinkit.com/v1/layout/search?q={encoded_query}&search_type=type_to_search"
                resp = await session.post(layout_url, headers=headers, json={}, timeout=10)

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
                v1_url = f"https://blinkit.com/v1/search?q={quote_plus(clean_query)}&lat=12.9716&lon=77.5946"
                resp_v1 = await session.get(v1_url, headers=headers, timeout=10)
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
                                return {
                                    "platform": "Blinkit",
                                    "price": price,
                                    "mrp": float(item.get("mrp") or 0) or None,
                                    "currency": "INR",
                                    "in_stock": bool(item.get("inventory", 1) > 0),
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
        pw_instance = None
        browser = None
        candidate = None
        try:
            pw_instance = await async_playwright().start()
            browser = await pw_instance.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="en-IN",
                geolocation={"latitude": 12.9716, "longitude": 77.5946},
                permissions=["geolocation"],
            )
            api_data = None
            async def on_response(response):
                nonlocal api_data
                if "layout/search" in response.url and not api_data:
                    try:
                        api_data = await response.json()
                    except Exception:
                        pass

            page.on("response", on_response)
            await page.goto(search_url, timeout=25000, wait_until="networkidle")
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

                    pid = d.get("product_id") or d.get("identity", {}).get("id") or "prod"
                    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
                    if score > best_score:
                        best_score = score
                        candidate = {
                            "platform": "Blinkit",
                            "price": price,
                            "mrp": None,
                            "currency": "INR",
                            "in_stock": True,
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
            return num
        except ValueError:
            return 0.0

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str):
        """Scooboo Shopify suggest JSON search API with canonical product page variant extraction."""
        import aiohttp
        from datetime import datetime, timezone
        from urllib.parse import quote_plus

        raw_query = f"{brand} {product_name}".strip()
        cleaned = re.sub(r"^['\"=\+\-@]+(?:\w+\(.*?\)|cmd\|.*?!A\d+|[\d\*\+\-/]+)?\s*", "", raw_query).strip()
        clean_query = " ".join((cleaned or raw_query).split())
        query = quote_plus(clean_query)
        api_url = f"https://scooboo.in/search/suggest.json?q={query}&resources[type]=product"
        headers = {
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(api_url, headers=headers) as resp:
                    self.check_bot_detection(resp.status, "")
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    products = data.get("resources", {}).get("results", {}).get("products", [])

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

                    score = self.compute_match_score(title, product_name, brand, barcode)
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
                available = True

                try:
                    async with session.get(detail_url, headers=headers) as detail_resp:
                        if detail_resp.status == 200:
                            detail_data = await detail_resp.json()
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
                                available = bool(v0.get("available", True))
                except Exception as dex:
                    logger.debug(f"[Scooboo] Product detail fetch error for {handle}: {dex}")

                if price <= 0:
                    # Fallback to suggest price if detail fetch failed
                    price = self._parse_shopify_price(best_candidate_prod.get("price"))
                    mrp_raw = best_candidate_prod.get("compare_at_price_max") or best_candidate_prod.get("compare_at_price")
                    mrp = self._parse_shopify_price(mrp_raw) if mrp_raw else None
                    available = bool(best_candidate_prod.get("available", True))

                if price <= 0:
                    return None

                return {
                    "platform": "Scooboo",
                    "price": price,
                    "mrp": mrp,
                    "currency": "INR",
                    "in_stock": available,
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

