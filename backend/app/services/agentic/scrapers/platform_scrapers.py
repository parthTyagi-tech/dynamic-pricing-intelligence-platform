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
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            # Target only organic search result cards (exclude sponsored ads)
            items = soup.select('div[data-component-type="s-search-result"]:not(.AdHolder)')
            target_lower = target_name.lower()
            is_refill_target = "refill" in target_lower

            for item in items:
                # Exclude sponsored badge or ad markers
                if item.select_one(".puis-sponsored-label-text, .s-sponsored-label-text, .AdHolder"):
                    continue

                title_node = item.find("h2")
                if not title_node:
                    continue
                title = title_node.get_text(strip=True)
                title_lower = title.lower()

                # Exclude refills if catalog query is a single unit pen
                if "refill" in title_lower and not is_refill_target:
                    continue

                score = self.compute_match_score(title, target_name, brand, barcode)
                if score < MATCH_THRESHOLD:
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

                if score > best_score:
                    best_score = score
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

    async def _tier2_mobile_headers(
        self, task_id: str, product_id: str, organization_id: str,
        product_name: str, brand: str, barcode: str, proxy: Optional[str],
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

        return self._extract_amazon_cards(html_text, product_name, brand, barcode, search_url)

    async def _tier3_playwright(
        self, task_id: str, product_id: str, organization_id: str,
        product_name: str, brand: str, barcode: str,
    ) -> Optional[Dict[str, Any]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.info(f"[{self.platform_name}] tier3 skipped: playwright not installed")
            return None

        query = product_name.strip()
        if brand and brand.lower() not in product_name.lower():
            query = f"{brand} {product_name}".strip()
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

        candidate = self._extract_amazon_cards(html_text, product_name, brand, barcode, search_url)
        if candidate:
            candidate["scrape_mode"] = "playwright"
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
        self, html_text: str, target_name: str, brand: str, barcode: str, search_url: str
    ) -> Optional[Dict[str, Any]]:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_text, "html.parser")
            best_candidate = None
            best_score = 0.0

            cards = soup.select("div[data-id]") or soup.find_all("div", attrs={"data-id": True})
            for card in cards:
                title_node = (
                    card.select_one("a.pIpigb, a.wjcEIp, div.KzDlHZ, div._4rR01T, a.s1Q9rs, a.VJA3rP, a[title]")
                    or card.find("a", href=True)
                )
                if not title_node:
                    continue
                title = title_node.get_text(strip=True) or title_node.get("title") or ""
                score = self.compute_match_score(title, target_name, brand, barcode)
                if score < MATCH_THRESHOLD:
                    continue

                price_node = card.select_one(".hZ3P6w, .Nx9bqj, ._30jeq3, div.col-5-12 ._30jeq3")
                if not price_node:
                    match = re.search(r"(?:₹|Rs\.?)\s*([\d,]+(?:\.\d{2})?)", card.get_text(strip=True))
                    if match:
                        clean_p = match.group(1).replace(",", "")
                    else:
                        continue
                else:
                    clean_p = re.sub(r"[^\d.]", "", price_node.get_text(strip=True).replace(",", ""))
                try:
                    price = float(clean_p)
                except ValueError:
                    continue
                if price <= 0:
                    continue

                # MRP
                mrp = None
                mrp_node = card.select_one(".kRYCnD, .yRaY8j, ._3I9_wc")
                if mrp_node:
                    clean_m = re.sub(r"[^\d.]", "", mrp_node.get_text(strip=True).replace(",", ""))
                    try:
                        mrp_val = float(clean_m)
                        if mrp_val >= price:
                            mrp = mrp_val
                    except ValueError:
                        pass

                # Live Product URL
                link_node = card.select_one("a.pIpigb[href], a._1fQZEK[href], a.wjcEIp[href], a.s1Q9rs[href], a.VJA3rP[href], a[href]")
                prod_url = search_url
                url_verified = False
                if link_node and link_node.get("href"):
                    href = link_node["href"]
                    if href.startswith("/"):
                        clean_href = href.split("?")[0]
                        prod_url = f"https://www.flipkart.com{clean_href}"
                        url_verified = True
                    elif href.startswith("http"):
                        prod_url = href.split("?")[0] if "flipkart.com" in href else href
                        url_verified = True

                if score > best_score:
                    best_score = score
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
        product_name: str, brand: str, barcode: str, proxy: Optional[str],
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
                    candidate = self._extract_flipkart_cards(html_text, product_name, brand, barcode, search_url)
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
                locale="en-IN",
                viewport={"width": 1366, "height": 768},
            )
            # Route abort heavy images for rapid execution
            await page.route(re.compile(r"\.(png|jpg|jpeg|gif|webp|ico)(\?.*)?$"), lambda r: r.abort())
            await page.goto(search_url, timeout=25000, wait_until="domcontentloaded")
            try:
                await page.wait_for_selector("div[data-id]", timeout=6000)
            except Exception:
                pass
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

        candidate = self._extract_flipkart_cards(html_text, product_name, brand, barcode, search_url)
        if candidate:
            candidate["scrape_mode"] = "playwright"
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
        product_name: str, brand: str, barcode: str, proxy: Optional[str],
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
        return await super()._tier2_mobile_headers(task_id, product_id, organization_id, product_name, brand, barcode, proxy)


class AjioScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Ajio",
            search_url_template="https://www.ajio.com/search/?text={query}",
            base_url="https://www.ajio.com",
        )

    async def _tier2_mobile_headers(
        self, task_id: str, product_id: str, organization_id: str,
        product_name: str, brand: str, barcode: str, proxy: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Use curl_cffi for TLS/JA3 and HTTP/2 client impersonation with aiohttp fallback."""
        query = f"{brand} {product_name}".strip()
        search_url = self.build_search_url(query)
        try:
            from curl_cffi.requests import AsyncSession
            async with AsyncSession(impersonate="chrome124") as session:
                resp = await session.get(search_url, timeout=12)
                if resp.status_code == 200:
                    self.check_bot_detection(resp.status_code, resp.text)
                    price, title = self._extract_price_and_title(resp.text)
                    match_score = self.compute_match_score(title, product_name, brand, barcode)
                    if match_score >= MATCH_THRESHOLD and price > 0:
                        product_url, url_verified = self._extract_product_link(resp.text, fallback_url=search_url)
                        return {
                            "platform": self.platform_name, "price": price,
                            "currency": "INR", "in_stock": True,
                            "product_url": product_url, "url_verified": url_verified,
                            "product_title": self.sanitize_output(title),
                            "scraped_at": datetime.now(timezone.utc).isoformat(),
                            "match_score": match_score, "unverified_match": False,
                            "scrape_mode": "curl_cffi_tls", "data_source": "live_scrape",
                        }
        except ImportError:
            logger.info("[Ajio] curl_cffi not installed; falling back to aiohttp.")
        except (PlatformRateLimitError, BotDetectionEncountered) as bde:
            raise bde
        except Exception as e:
            logger.warning(f"[Ajio] curl_cffi request failed: {e}")
        # Fall back to base aiohttp tier2
        return await super()._tier2_mobile_headers(task_id, product_id, organization_id, product_name, brand, barcode, proxy)


class NykaaScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Nykaa",
            search_url_template="https://www.nykaa.com/search/result/?q={query}",
            base_url="https://www.nykaa.com",
        )


class PurplleScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Purplle",
            search_url_template="https://www.purplle.com/search?q={query}",
            base_url="https://www.purplle.com",
        )


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


class JioMartScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="JioMart",
            search_url_template="https://www.jiomart.com/search/{query}",
            base_url="https://www.jiomart.com",
        )


class PepperfryScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Pepperfry",
            search_url_template="https://www.pepperfry.com/site_product/search?q={query}",
            base_url="https://www.pepperfry.com",
        )


class UrbanLadderScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Urban Ladder",
            search_url_template="https://www.urbanladder.com/products/search?keywords={query}",
            base_url="https://www.urbanladder.com",
        )


class OneMgScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="1mg",
            search_url_template="https://www.1mg.com/search/all?name={query}",
            base_url="https://www.1mg.com",
        )


class PharmEasyScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="PharmEasy",
            search_url_template="https://pharmeasy.in/search/all?name={query}",
            base_url="https://pharmeasy.in",
        )


class CaratLaneScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="CaratLane",
            search_url_template="https://www.caratlane.com/search/{query}",
            base_url="https://www.caratlane.com",
        )


class TanishqScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Tanishq",
            search_url_template="https://www.tanishq.co.in/shop?q={query}",
            base_url="https://www.tanishq.co.in",
        )


class CromaScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Croma",
            search_url_template="https://www.croma.com/searchB?q={query}%3Arelevance&text={query}",
            base_url="https://www.croma.com",
        )


class MeeshoScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Meesho",
            search_url_template="https://www.meesho.com/search?q={query}",
            base_url="https://www.meesho.com",
        )


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

