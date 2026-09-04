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


PLATFORM_SCRAPERS: Dict[str, BaseScraperAgent] = {
    "Amazon.in": AmazonScraperAgent(),
    "Flipkart": FlipkartScraperAgent(),
    "Myntra": MyntraScraperAgent(),
    "Ajio": AjioScraperAgent(),
    "Nykaa": NykaaScraperAgent(),
    "Purplle": PurplleScraperAgent(),
    "BigBasket": BigBasketScraperAgent(),
    "JioMart": JioMartScraperAgent(),
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
    "myntra": "Myntra",
    "ajio": "Ajio",
    "nykaa": "Nykaa",
    "purplle": "Purplle",
    "bigbasket": "BigBasket",
    "jiomart": "JioMart",
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


def get_scraper_for_platform(platform_name: str) -> BaseScraperAgent:
    """
    Returns the scraper instance for a given platform name.

    Raises:
        ValueError: If platform_name is unknown or unsupported. Never silently
                    falls back to another platform to prevent data corruption.
    """
    if not platform_name or not isinstance(platform_name, str):
        raise ValueError("Platform name must be a non-empty string.")

    cleaned_name = platform_name.strip()

    # Exact match in registry
    if cleaned_name in PLATFORM_SCRAPERS:
        return PLATFORM_SCRAPERS[cleaned_name]

    # Normalized alias match (case-insensitive, whitespace-insensitive)
    normalized = cleaned_name.lower().replace("_", " ").replace("-", " ")
    if normalized in PLATFORM_ALIASES:
        canonical = PLATFORM_ALIASES[normalized]
        return PLATFORM_SCRAPERS[canonical]

    # Unknown platform: Raise explicit ValueError to avoid silent cross-platform pollution
    valid_platforms = ", ".join(sorted(PLATFORM_SCRAPERS.keys()))
    raise ValueError(
        f"Unsupported platform: '{platform_name}'. "
        f"No scraper registered for this marketplace. Supported platforms: {valid_platforms}"
    )
