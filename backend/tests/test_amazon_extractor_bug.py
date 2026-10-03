from pathlib import Path
from app.services.agentic.scrapers.platform_scrapers import AmazonScraperAgent

def test_amazon_extractor_headers_branch_does_not_raise_name_error():
    fixture_path = Path(__file__).parent / "fixtures" / "amazon_search_headers_branch.html"
    html_text = fixture_path.read_text(encoding="utf-8")

    scraper = AmazonScraperAgent()
    candidate = scraper._extract_amazon_cards(
        html_text=html_text,
        target_name="Apple iPhone 15 128GB Black",
        brand="Apple",
        barcode="",
        search_url="https://www.amazon.in/s?k=test",
        catalog_price=79900.0
    )

    assert candidate is not None, "Expected candidate extracted from headers branch without NameError"
    assert candidate["platform"] == "Amazon.in"
    assert candidate["price"] == 74999.0
    assert candidate["mrp"] == 79900.0
    assert "B0CHX1W1XY" in candidate["product_url"]
