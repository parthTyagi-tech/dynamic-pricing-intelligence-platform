import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.realtime_scraper import PLATFORMS, extract_price_from_html
from app.services.email_service import send_recommendation_action_email


PLATFORM_NAMES = {platform["name"] for platform in PLATFORMS}


def test_catalog_platform_contract_is_exactly_eight_marketplaces():
    assert PLATFORM_NAMES == {"Amazon", "Flipkart", "Ajio", "Croma", "Myntra", "Nykaa", "Reliance Digital", "Tata CLiQ"}


def test_structured_data_extracts_catalog_price_for_every_platform_fixture():
    catalog_path = Path(__file__).resolve().parents[2] / "catalog_sample.csv"
    with catalog_path.open(newline="") as handle:
        catalog_rows = list(csv.DictReader(handle))
    assert catalog_rows
    for row in catalog_rows:
        expected_price = float(row["current_price"])
        for platform_name in sorted(PLATFORM_NAMES):
            html = f'''<html><head><script type="application/ld+json">{{"@type":"Product","sku":"{row["sku"]}","name":"{row["name"]}","offers":{{"price":"{expected_price:.2f}","priceCurrency":"INR","availability":"https://schema.org/InStock"}}}}</script></head></html>'''
            result = extract_price_from_html(html)
            assert result is not None, f"{platform_name}:{row['sku']}"
            assert result["price"] == expected_price
            assert result["currency"] == "INR"
            assert result["in_stock"] is True
            assert result["extraction_strategy"] == "jsonld"


def test_metadata_and_dom_fallbacks_are_deterministic():
    metadata = '<meta property="og:price:amount" content="₹1,299.00"><meta property="og:price:currency" content="INR">'
    assert extract_price_from_html(metadata)["price"] == 1299.0
    dom = '<main>Limited offer — ₹2,499.00. In stock.</main>'
    assert extract_price_from_html(dom)["price"] == 2499.0
    usd = '<main>Price $100.00</main>'
    assert extract_price_from_html(usd)["price"] == 8330.0


def test_brevo_service_is_safe_without_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    monkeypatch.setenv("EMAIL_ARCHIVE_DIR", str(tmp_path))
    result = send_recommendation_action_email(
        user_email="audit@example.com",
        action_type="approve",
        product_details={"name": "Fixture product", "sku": "FIX-1", "category": "electronics"},
        recommendation_details={"previous_price": 1000, "executed_price": 950, "rationale": "Improved conversion probability."},
        competitor_prices=[],
        action_id="action-1",
        user_role="admin",
    )
    assert result["status"] == "mocked"
    assert result["provider"] in {"brevo", "local_archive"}


def test_mock_scraper_emits_structured_selected_platform_results(monkeypatch):
    import asyncio
    import json
    from app.services.realtime_scraper import stream_multi_platform_prices

    monkeypatch.setenv("MOCK_SCRAPER", "true")

    async def collect():
        return [chunk async for chunk in stream_multi_platform_prices(
            search_query="iPhone 15",
            brand="Apple",
            category="electronics",
            baseline_price_inr=79900,
            platforms=["Amazon", "Flipkart"],
        )]

    chunks = asyncio.run(collect())
    events = [json.loads(chunk[6:].strip()) for chunk in chunks if chunk.startswith("data: ")]
    results = [event["data"] for event in events if event.get("status") == "success"]

    assert {result["platform_name"] for result in results} == {"Amazon", "Flipkart"}
    assert all(result["price"] > 0 for result in results)
    assert all(result["fetch_method"] == "Mock fixture" for result in results)
    assert all(result["url"].startswith("https://") for result in results)
    assert all(result["scraped_at"] for result in results)
    assert events[-1]["status"] == "completed"
    assert events[-1]["mock"] is True


def test_normalize_price_handles_currency_and_thousands_separator():
    from app.services.realtime_scraper import normalize_price

    assert normalize_price("₹79,900", "INR") == 79900.0
    assert normalize_price("$100", "USD") == 8330.0
    assert normalize_price("€100", "EUR") == 9000.0
