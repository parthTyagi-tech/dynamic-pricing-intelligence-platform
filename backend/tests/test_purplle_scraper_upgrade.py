import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.agentic.scrapers.platform_scrapers import PurplleScraperAgent
from app.services.agentic.scrapers.base_scraper import PlatformRateLimitError, BotDetectionEncountered

SAMPLE_API_JSON = {
    "items": [
        {
            "id": "12345",
            "name": "Maybelline New York Colossal Kajal",
            "item_name": "Maybelline New York Colossal Kajal",
            "our_price": 175.0,
            "mrp": 220.0,
            "slug": "maybelline-new-york-colossal-kajal-black-0-35-g",
            "in_stock": True
        }
    ]
}

SAMPLE_DOM_HTML = """
<html>
<body>
  <div class="product-listing">
    <div class="product-card">
      <a href="/product/maybelline-new-york-colossal-kajal-black-0-35-g">
        <p class="title">Maybelline New York Colossal Kajal</p>
        <span class="price">₹175</span>
        <span class="mrp">₹220</span>
      </a>
    </div>
  </div>
</body>
</html>
"""

@pytest.mark.asyncio
async def test_purplle_tier1_internal_api_success():
    agent = PurplleScraperAgent()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps(SAMPLE_API_JSON)
    mock_resp.json.return_value = SAMPLE_API_JSON

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_resp)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api(
            product_name="Maybelline New York Colossal Kajal",
            brand="Maybelline",
            barcode="",
            catalog_price=180.0,
        )

    assert candidate is not None
    assert candidate["platform"] == "Purplle"
    assert candidate["price"] == 175.0
    assert candidate["mrp"] == 220.0
    assert "Maybelline" in candidate["product_title"]
    assert "maybelline-new-york-colossal-kajal" in candidate["product_url"]
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"
    assert candidate["scrape_mode"] == "internal_api"
    assert candidate["match_score"] >= 0.70

def test_purplle_extract_cards_structured_data_delegation():
    agent = PurplleScraperAgent()

    structured_candidate = {
        "platform": "Purplle",
        "price": 175.0,
        "mrp": 220.0,
        "currency": "INR",
        "in_stock": True,
        "stock_status": "in_stock",
        "product_url": "https://www.purplle.com/product/maybelline-kajal",
        "url_verified": True,
        "product_title": "Maybelline New York Colossal Kajal",
        "scraped_at": "2026-10-20T18:00:00Z",
        "match_score": 0.95,
        "unverified_match": False,
        "scrape_mode": "structured_data",
        "data_source": "live_scrape",
    }

    with patch.object(agent, "_extract_structured_data", return_value=structured_candidate):
        candidate = agent._extract_cards(
            html_text="<html><body>Sample</body></html>",
            target_name="Maybelline New York Colossal Kajal",
            brand="Maybelline",
            barcode="",
            search_url="https://www.purplle.com/search?q=kajal",
            catalog_price=180.0,
        )

    assert candidate is not None
    assert candidate["price"] == 175.0
    assert candidate["scrape_mode"] == "structured_data"

def test_purplle_extract_cards_dom_fallback():
    agent = PurplleScraperAgent()
    candidate = agent._extract_cards(
        html_text=SAMPLE_DOM_HTML,
        target_name="Maybelline New York Colossal Kajal",
        brand="Maybelline",
        barcode="",
        search_url="https://www.purplle.com/search?q=kajal",
        catalog_price=180.0,
    )

    assert candidate is not None
    assert candidate["platform"] == "Purplle"
    assert candidate["price"] == 175.0
    assert candidate["mrp"] == 220.0
    assert "Maybelline" in candidate["product_title"]
    assert "maybelline-new-york-colossal-kajal" in candidate["product_url"]
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"
    assert candidate["scrape_mode"] == "mobile_headers"
    assert candidate["match_score"] >= 0.70

@pytest.mark.asyncio
async def test_purplle_catalog_price_ranking():
    agent = PurplleScraperAgent()

    multi_item_json = {
        "items": [
            {
                "id": "1",
                "name": "Maybelline New York Colossal Kajal Combo 4 Pack",
                "our_price": 750.0,
                "mrp": 900.0,
                "slug": "combo-pack-4",
            },
            {
                "id": "2",
                "name": "Maybelline New York Colossal Kajal Single",
                "our_price": 175.0,
                "mrp": 220.0,
                "slug": "single-kajal",
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps(multi_item_json)
    mock_resp.json.return_value = multi_item_json

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_resp)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api(
            product_name="Maybelline New York Colossal Kajal",
            brand="Maybelline",
            barcode="",
            catalog_price=180.0,
        )

    assert candidate is not None
    # Candidate closest to catalog_price 180.0 should be chosen over 750.0 combo
    assert candidate["price"] == 175.0

@pytest.mark.asyncio
async def test_purplle_bot_detection_and_rate_limit():
    agent = PurplleScraperAgent()

    # Rate limit test (HTTP 429)
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.text = "Too Many Requests"

    mock_session_429 = AsyncMock()
    mock_session_429.get = AsyncMock(return_value=resp_429)
    mock_session_429.__aenter__.return_value = mock_session_429
    mock_session_429.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session_429):
        with pytest.raises(PlatformRateLimitError):
            await agent._tier1_internal_api(
                product_name="Maybelline Kajal",
                brand="Maybelline",
                barcode="",
            )

    # Radware HTTP 471 Request Blocked test
    resp_471 = MagicMock()
    resp_471.status_code = 471
    resp_471.text = "<html><head><title>Request Blocked</title></head><body>Request Blocked by security policy</body></html>"

    mock_session_471 = AsyncMock()
    mock_session_471.get = AsyncMock(return_value=resp_471)
    mock_session_471.__aenter__.return_value = mock_session_471
    mock_session_471.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session_471):
        with pytest.raises(BotDetectionEncountered):
            await agent._tier1_internal_api(
                product_name="Maybelline Kajal",
                brand="Maybelline",
                barcode="",
            )
