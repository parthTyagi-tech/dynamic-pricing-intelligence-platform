from typing import Dict
from app.services.agentic.scrapers.base_scraper import BaseScraperAgent


class AmazonScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Amazon.in",
            search_url_template="https://www.amazon.in/s?k={query}",
            base_url="https://www.amazon.in",
        )


class FlipkartScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Flipkart",
            search_url_template="https://www.flipkart.com/search?q={query}",
            base_url="https://www.flipkart.com",
        )


class MyntraScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Myntra",
            search_url_template="https://www.myntra.com/{query}",
            base_url="https://www.myntra.com",
        )


class AjioScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Ajio",
            search_url_template="https://www.ajio.com/search/?text={query}",
            base_url="https://www.ajio.com",
        )


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
        self.headers = {
            "lat": "28.6139",
            "lon": "77.2090",
            "app_client": "consumer_web",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str):
        """Blinkit internal search API with coordinate headers (lat/lon)."""
        import aiohttp
        from datetime import datetime, timezone
        from urllib.parse import quote_plus

        query = quote_plus(f"{brand} {product_name}".strip())
        api_url = f"https://blinkit.com/v1/search?q={query}"
        headers = self.headers
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                async with session.get(api_url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        products = data.get("products") or data.get("items") or []
                        if products and isinstance(products, list):
                            first = products[0]
                            title = first.get("name") or first.get("title") or product_name
                            price = float(first.get("price") or first.get("discounted_price") or 0)
                            match_score = self.compute_match_score(title, product_name, brand, barcode)
                            p_slug = first.get("product_id") or first.get("id") or query
                            return {
                                "platform": "Blinkit",
                                "price": price,
                                "currency": "INR",
                                "in_stock": True,
                                "product_url": f"https://blinkit.com/prn/{p_slug}",
                                "url_verified": True,
                                "product_title": self.sanitize_output(title),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "match_score": match_score,
                                "unverified_match": False,
                                "scrape_mode": "internal_api",
                                "data_source": "live_scrape",
                            }
        except Exception:
            pass
        return None


class ScoobooScraperAgent(BaseScraperAgent):
    def __init__(self):
        super().__init__(
            platform_name="Scooboo",
            search_url_template="https://scooboo.in/search?q={query}",
            base_url="https://scooboo.in",
        )

    async def _tier1_internal_api(self, product_name: str, brand: str, barcode: str):
        """Scooboo Shopify suggest JSON search API."""
        import aiohttp
        from datetime import datetime, timezone
        from urllib.parse import quote_plus

        query = quote_plus(f"{brand} {product_name}".strip())
        api_url = f"https://scooboo.in/search/suggest.json?q={query}&resources[type]=product"
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
                async with session.get(api_url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        products = data.get("resources", {}).get("results", {}).get("products", [])
                        if products and isinstance(products, list):
                            first = products[0]
                            title = first.get("title") or product_name
                            price_raw = first.get("price") or 0.0
                            try:
                                price = float(price_raw)
                            except (ValueError, TypeError):
                                price = 0.0
                            match_score = self.compute_match_score(title, product_name, brand, barcode)
                            handle = first.get("handle") or ""
                            product_url = f"https://scooboo.in/products/{handle}" if handle else f"https://scooboo.in/search?q={query}"
                            return {
                                "platform": "Scooboo",
                                "price": price,
                                "currency": "INR",
                                "in_stock": True,
                                "product_url": product_url,
                                "url_verified": bool(handle),
                                "product_title": self.sanitize_output(title),
                                "scraped_at": datetime.now(timezone.utc).isoformat(),
                                "match_score": match_score,
                                "unverified_match": False,
                                "scrape_mode": "internal_api",
                                "data_source": "live_scrape",
                            }
        except Exception:
            pass
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

