"""
backend/app/services/agentic/scrapers/schemas.py

Pydantic contract every scraper tier must satisfy before a result is
accepted into the pipeline. Validating at this boundary means a malformed
or malicious scrape result (bad URL, non-HTTPS product_url, negative price)
never reaches the debate agents or the DB.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class ScrapedOffer(BaseModel):
    platform: str
    product_title: str
    price: float
    mrp: Optional[float] = None
    currency: str = "INR"
    in_stock: bool
    product_url: str
    match_score: float = Field(ge=0.0, le=1.0)
    scraped_at: datetime

    # Extra provenance fields (not in the original spec's minimal schema, but
    # required by Slice 4's Supervisor guardrail to explain *how* an offer
    # was obtained and how much to trust it during degraded operation).
    scrape_mode: str = "unknown"          # internal_api | mobile_headers | playwright | mock_simulation
    data_source: str = "live_scrape"      # live_scrape | estimated_fallback | mock_simulation
    unverified_match: bool = False
    url_verified: bool = True             # False if product_url had to fall back to the search page

    @field_validator("product_url")
    @classmethod
    def https_only(cls, v: str) -> str:
        # SEC-12: refuse non-HTTPS destination links before they can ever be
        # shown to an analyst or emailed in an approval notification.
        from app.utils.security_guardrails import is_https_url

        if not is_https_url(v):
            raise ValueError(f"product_url must be HTTPS: {v!r}")
        return v

    @field_validator("price")
    @classmethod
    def positive_price(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("price must be > 0")
        return v

    @field_validator("mrp")
    @classmethod
    def mrp_not_below_price(cls, v: Optional[float], info) -> Optional[float]:
        price = info.data.get("price")
        if v is not None and price is not None and v < price:
            # MRP below the actual selling price is almost always a scrape
            # error (wrong DOM node), not a real discount > 100%.
            raise ValueError(f"mrp ({v}) is below price ({price}) — likely a scrape error")
        return v
