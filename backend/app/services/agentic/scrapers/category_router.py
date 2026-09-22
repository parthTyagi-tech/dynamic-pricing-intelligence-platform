"""
backend/app/services/agentic/scrapers/category_router.py

Routes a Product to the ordered list of platform scrapers it should
actually be checked against, instead of the previous implicit behavior
of every platform being reachable for every product regardless of fit.

Routing precedence (most specific wins):
  1. product.category_hint, matched against free-text overrides
     (handles sub-categories that don't have a first-class ProductCategory,
     e.g. "pharmacy", "jewelry" — both present in PLATFORM_SCRAPERS today
     via 1mg/PharmEasy/CaratLane/Tanishq but with no category to route from).
  2. product.category, matched against the ProductCategory enum map.
  3. A conservative default (general marketplaces only) — never "all
     platforms", since that would let e.g. a t-shirt get priced against
     BigBasket grocery listings with a low but nonzero match_score.
"""

from typing import List

from app.models.product import ProductCategory
from app.services.agentic.scrapers.platform_scrapers import (
    PLATFORM_SCRAPERS,
    BaseScraperAgent,
)

CATEGORY_PLATFORM_MAP = {
    ProductCategory.ELECTRONICS: ["Amazon.in", "Flipkart", "JioMart"],
    ProductCategory.APPAREL: ["Myntra", "Ajio", "Amazon.in", "Flipkart"],
    ProductCategory.HOME_GOODS: ["Pepperfry", "Urban Ladder", "Amazon.in", "Flipkart", "JioMart"],
    ProductCategory.BEAUTY: ["Nykaa", "Purplle", "Amazon.in", "Flipkart"],
    ProductCategory.SPORTS: ["Amazon.in", "Flipkart", "Ajio"],
}

# category_hint values that route to platforms with no ProductCategory of
# their own (1mg/PharmEasy/CaratLane/Tanishq were in PLATFORM_SCRAPERS but
# were unreachable by any routing path before this file existed).
CATEGORY_HINT_OVERRIDES = {
    "pharmacy": ["1mg", "PharmEasy"],
    "medicine": ["1mg", "PharmEasy"],
    "otc": ["1mg", "PharmEasy"],
    "jewelry": ["CaratLane", "Tanishq"],
    "jewellery": ["CaratLane", "Tanishq"],
    "grocery": ["BigBasket", "JioMart"],
    "fmcg": ["BigBasket", "JioMart"],
}

DEFAULT_PLATFORMS = ["Amazon.in", "Flipkart"]

MAX_PLATFORMS_PER_PRODUCT = 5  # scrape-budget guardrail


class NoEligiblePlatformsError(ValueError):
    """Raised when routing produces an empty platform list."""


def get_eligible_platforms(product) -> List[str]:
    """
    product: duck-typed — accepts a Product ORM instance or any object/dict
    exposing category_hint/category.
    """
    def _get(attr):
        if isinstance(product, dict):
            return product.get(attr)
        return getattr(product, attr, None)

    hint = (_get("category_hint") or "").strip().lower()
    if hint in CATEGORY_HINT_OVERRIDES:
        return list(CATEGORY_HINT_OVERRIDES[hint])

    category = _get("category")
    if category in CATEGORY_PLATFORM_MAP:
        return list(CATEGORY_PLATFORM_MAP[category])[:MAX_PLATFORMS_PER_PRODUCT]

    return list(DEFAULT_PLATFORMS)


def get_scrapers_for_product(product) -> List[BaseScraperAgent]:
    platforms = get_eligible_platforms(product)
    scrapers = [PLATFORM_SCRAPERS[p] for p in platforms if p in PLATFORM_SCRAPERS]

    if not scrapers:
        category = product.get("category") if isinstance(product, dict) else getattr(product, "category", None)
        hint = product.get("category_hint") if isinstance(product, dict) else getattr(product, "category_hint", None)
        raise NoEligiblePlatformsError(
            f"No eligible scraper platforms resolved for category={category!r} "
            f"hint={hint!r}. This should route to the Supervisor's graceful "
            "degradation path (Slice 4), not raise all the way to the user."
        )

    return scrapers
