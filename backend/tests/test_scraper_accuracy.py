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
