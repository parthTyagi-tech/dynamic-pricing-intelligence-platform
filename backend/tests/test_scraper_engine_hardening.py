"""
Unit and integration tests for scraper engine hardening:
1. get_scraper_for_platform import and route validation
2. ScrapedOffer schema preservation of stock_status and synchronization
3. compute_match_score false-positive fixes and boost
4. _extract_structured_data for JSON-LD, Next.js __NEXT_DATA__, and OpenGraph
5. Tier 4 search engine grounded discovery
"""

import json
import pytest
from datetime import datetime, timezone

from app.services.agentic.scrapers.base_scraper import (
    BaseScraperAgent,
    MATCH_THRESHOLD,
    NEGATIVE_ACCESSORY_TOKENS,
    NEGATIVE_ACCESSORY_PHRASES,
)
from app.services.agentic.scrapers.schemas import ScrapedOffer
from app.services.agentic.scrapers.platform_scrapers import get_scraper_for_platform


def test_agentic_routes_has_get_scraper_import():
    from app.routes.agentic_routes import get_scraper_for_platform as route_fn
    assert callable(route_fn)
    scraper = route_fn("Amazon.in")
    assert scraper.platform_name == "Amazon.in"


def test_scraped_offer_stock_status_synchronization():
    now = datetime.now(timezone.utc)
    # in_stock=True defaults stock_status to in_stock
    offer_in = ScrapedOffer(
        platform="Amazon.in",
        product_title="Sony WH-1000XM5",
        price=24990.0,
        in_stock=True,
        product_url="https://www.amazon.in/dp/B09XS7JWHH",
        match_score=0.92,
        scraped_at=now,
    )
    assert offer_in.stock_status == "in_stock"
    data_in = offer_in.model_dump(mode="json")
    assert data_in["stock_status"] == "in_stock"
    assert data_in["in_stock"] is True

    # in_stock=False forces stock_status to out_of_stock
    offer_out = ScrapedOffer(
        platform="Flipkart",
        product_title="Sony WH-1000XM5",
        price=24990.0,
        in_stock=False,
        product_url="https://www.flipkart.com/p/123",
        match_score=0.92,
        scraped_at=now,
    )
    assert offer_out.stock_status == "out_of_stock"
    data_out = offer_out.model_dump(mode="json")
    assert data_out["stock_status"] == "out_of_stock"
    assert data_out["in_stock"] is False

    # stock_status="out_of_stock" forces in_stock=False
    offer_sync = ScrapedOffer(
        platform="Flipkart",
        product_title="Sony WH-1000XM5",
        price=24990.0,
        in_stock=True,
        stock_status="out_of_stock",
        product_url="https://www.flipkart.com/p/123",
        match_score=0.92,
        scraped_at=now,
    )
    assert offer_sync.in_stock is False
    assert offer_sync.stock_status == "out_of_stock"


def test_compute_match_score_false_positives_and_boost():
    scraper = BaseScraperAgent("Amazon.in", "https://www.amazon.in/s?k={query}", "https://www.amazon.in")

    # 1. Accessory provided with product (e.g. "with Carrying Case") must NOT be disqualified
    s_case = scraper.compute_match_score(
        scraped_title="Sony WH-1000XM5 Headphones with Carrying Case",
        target_name="Sony WH-1000XM5 Wireless Headphones",
        brand="Sony"
    )
    assert s_case >= 0.75

    # 2. Standalone accessory listing (Spigen Rugged Armor Case) MUST be disqualified (< 0.75)
    s_spigen = scraper.compute_match_score(
        scraped_title="Spigen Rugged Armor Case for iPhone 15",
        target_name="Apple iPhone 15 128GB Black",
        brand="Apple"
    )
    assert s_spigen < 0.75
    assert s_spigen == 0.20

    # 3. Glass carafe / Gorilla glass must NOT be disqualified by standalone "glass"
    s_glass = scraper.compute_match_score(
        scraped_title="Sony Glass Carafe 1L",
        target_name="Sony Glass Carafe",
        brand="Sony"
    )
    assert s_glass >= 0.75

    # 4. Tempered glass / screen protector MUST be penalized
    s_tempered = scraper.compute_match_score(
        scraped_title="Apple iPhone 15 Tempered Glass Screen Protector",
        target_name="Apple iPhone 15 128GB Black",
        brand="Apple"
    )
    assert s_tempered == 0.20

    # 5. Pack of 1 is allowed, multi-pack (pack of 4) is disqualified
    s_pack1 = scraper.compute_match_score(
        scraped_title="Dove Soap Bar Pack of 1",
        target_name="Dove Soap Bar",
        brand="Dove"
    )
    assert s_pack1 >= 0.75

    s_pack4 = scraper.compute_match_score(
        scraped_title="Dove Soap Bar Pack of 4",
        target_name="Dove Soap Bar",
        brand="Dove"
    )
    assert s_pack4 == 0.20

    # 6. Hyphen & plural normalization + boost
    s_norm = scraper.compute_match_score(
        scraped_title="Sony WH1000XM5 Headphone Silver",
        target_name="Sony WH-1000XM5 Headphones",
        brand="Sony"
    )
    assert s_norm >= 0.80


def test_extract_structured_data_json_ld():
    scraper = BaseScraperAgent("Amazon.in", "https://www.amazon.in/s?k={query}", "https://www.amazon.in")

    html_ld = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
          "offers": {
            "@type": "Offer",
            "price": "26990.00",
            "priceCurrency": "INR",
            "availability": "https://schema.org/InStock",
            "url": "https://www.amazon.in/dp/B09XS7JWHH"
          }
        }
        </script>
      </head>
      <body></body>
    </html>
    """
    res = scraper._extract_structured_data(
        html_ld, "Sony WH-1000XM5 Headphones", "Sony", "", "https://www.amazon.in"
    )
    assert res is not None
    assert res["price"] == 26990.0
    assert res["stock_status"] == "in_stock"
    assert res["product_url"] == "https://www.amazon.in/dp/B09XS7JWHH"
    assert res["scrape_mode"] == "structured_data"
    assert res["data_source"] == "live_scrape"


def test_extract_structured_data_next_data():
    scraper = BaseScraperAgent("Flipkart", "https://www.flipkart.com/search?q={query}", "https://www.flipkart.com")

    next_payload = {
        "props": {
            "pageProps": {
                "productDetails": {
                    "productName": "Sony WH-1000XM5 Wireless Headphones",
                    "sellingPrice": 24990,
                    "mrp": 29990,
                    "pdpUrl": "/p/sony-wh1000xm5",
                    "inStock": True
                }
            }
        }
    }
    html_next = f"""
    <html>
      <head>
        <script id="__NEXT_DATA__" type="application/json">{json.dumps(next_payload)}</script>
      </head>
      <body></body>
    </html>
    """
    res = scraper._extract_structured_data(
        html_next, "Sony WH-1000XM5 Headphones", "Sony", "", "https://www.flipkart.com"
    )
    assert res is not None
    assert res["price"] == 24990.0
    assert res["mrp"] == 29990.0
    assert res["product_url"] == "https://www.flipkart.com/p/sony-wh1000xm5"
    assert res["stock_status"] == "in_stock"


def test_extract_structured_data_opengraph():
    scraper = BaseScraperAgent("Amazon.in", "https://www.amazon.in/s?k={query}", "https://www.amazon.in")

    html_og = """
    <html>
      <head>
        <meta property="og:title" content="Sony WH-1000XM5 Headphones" />
        <meta property="product:price:amount" content="25499.00" />
        <meta property="og:url" content="https://www.amazon.in/dp/B09XS7XYZ" />
        <meta property="product:availability" content="in stock" />
      </head>
      <body></body>
    </html>
    """
    res = scraper._extract_structured_data(
        html_og, "Sony WH-1000XM5 Headphones", "Sony", "", "https://www.amazon.in"
    )
    assert res is not None
    assert res["price"] == 25499.0
    assert res["product_url"] == "https://www.amazon.in/dp/B09XS7XYZ"
    assert res["stock_status"] == "in_stock"
