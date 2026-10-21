import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.agentic.scrapers.platform_scrapers import NykaaScraperAgent
from app.services.agentic.scrapers.base_scraper import PlatformRateLimitError, BotDetectionEncountered

SAMPLE_PRELOADED_STATE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <script>
    window.__PRELOADED_STATE__ = {
      "searchListingPage": {
        "listingData": {
          "products": [
            {
              "id": 12153,
              "title": "Maybelline New York The Colossal Kajal 24Hour Smudge Proof",
              "name": "Maybelline New York The Colossal Kajal 24Hour Smudge Proof",
              "price": 176.0,
              "mrp": 220.0,
              "slug": "maybelline-the-colossal-kajal-12-hour-smudge-free/p/12153",
              "inStock": true,
              "quantity": 500
            }
          ]
        }
      }
    };
  </script>
</head>
<body><div>Nykaa Products</div></body>
</html>
"""

SAMPLE_DOM_HTML = """
<html>
<body>
  <div class="productWrapper">
    <div data-test-id="product-card">
      <a class="css-qlopj5" href="/maybelline-the-colossal-kajal-12-hour-smudge-free/p/12153">
        <div class="css-xrzmfa">Maybelline New York The Colossal Kajal 24Hour Smudge Proof</div>
        <span class="css-111z9ua">₹176</span>
        <span class="css-17x46n5">₹220</span>
      </a>
    </div>
  </div>
</body>
</html>
"""

@pytest.mark.asyncio
async def test_nykaa_tier1_internal_api_success():
    agent = NykaaScraperAgent()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_PRELOADED_STATE_HTML

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_resp)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api(
            product_name="Maybelline New York The Colossal Kajal",
            brand="Maybelline",
            barcode="",
            catalog_price=180.0,
        )

    assert candidate is not None
    assert candidate["platform"] == "Nykaa"
    assert candidate["price"] == 176.0
    assert candidate["mrp"] == 220.0
    assert "Maybelline" in candidate["product_title"]
    assert "maybelline-the-colossal-kajal" in candidate["product_url"]
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"
    assert candidate["scrape_mode"] == "internal_api"
    assert candidate["match_score"] >= 0.70

def test_nykaa_extract_cards_structured_data_delegation():
    agent = NykaaScraperAgent()

    structured_candidate = {
        "platform": "Nykaa",
        "price": 176.0,
        "mrp": 220.0,
        "currency": "INR",
        "in_stock": True,
        "stock_status": "in_stock",
        "product_url": "https://www.nykaa.com/maybelline-kajal/p/12153",
        "url_verified": True,
        "product_title": "Maybelline New York The Colossal Kajal",
        "scraped_at": "2026-10-20T18:00:00Z",
        "match_score": 0.95,
        "unverified_match": False,
        "scrape_mode": "structured_data",
        "data_source": "live_scrape",
    }

    with patch.object(agent, "_extract_structured_data", return_value=structured_candidate):
        candidate = agent._extract_cards(
            html_text="<html><body>Sample</body></html>",
            target_name="Maybelline New York The Colossal Kajal",
            brand="Maybelline",
            barcode="",
            search_url="https://www.nykaa.com/search/result/?q=kajal",
            catalog_price=180.0,
        )

    assert candidate is not None
    assert candidate["price"] == 176.0
    assert candidate["scrape_mode"] == "structured_data"

def test_nykaa_extract_cards_dom_fallback():
    agent = NykaaScraperAgent()
    candidate = agent._extract_cards(
        html_text=SAMPLE_DOM_HTML,
        target_name="Maybelline New York The Colossal Kajal",
        brand="Maybelline",
        barcode="",
        search_url="https://www.nykaa.com/search/result/?q=kajal",
        catalog_price=180.0,
    )

    assert candidate is not None
    assert candidate["platform"] == "Nykaa"
    assert candidate["price"] == 176.0
    assert candidate["mrp"] == 220.0
    assert "Maybelline" in candidate["product_title"]
    assert "12153" in candidate["product_url"]
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"
    assert candidate["scrape_mode"] == "mobile_headers"
    assert candidate["match_score"] >= 0.70

@pytest.mark.asyncio
async def test_nykaa_catalog_price_ranking():
    agent = NykaaScraperAgent()

    multi_product_html = """
    <script>
      window.__PRELOADED_STATE__ = {
        "searchListingPage": {
          "listingData": {
            "products": [
              {
                "id": 9999,
                "title": "Maybelline New York Beauty Combo Pack of 5",
                "price": 1299.0,
                "mrp": 1999.0,
                "slug": "maybelline-beauty-combo-pack/p/9999",
                "inStock": true
              },
              {
                "id": 12153,
                "title": "Maybelline New York The Colossal Kajal 24Hour Smudge Proof",
                "price": 176.0,
                "mrp": 220.0,
                "slug": "maybelline-the-colossal-kajal-12-hour-smudge-free/p/12153",
                "inStock": true
              }
            ]
          }
        }
      };
    </script>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = multi_product_html

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_resp)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api(
            product_name="Maybelline New York The Colossal Kajal",
            brand="Maybelline",
            barcode="",
            catalog_price=180.0,
        )

    assert candidate is not None
    # Candidate closest to catalog_price 180.0 should be chosen over 1299.0 combo
    assert candidate["price"] == 176.0

@pytest.mark.asyncio
async def test_nykaa_bot_detection_and_rate_limit():
    agent = NykaaScraperAgent()

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

    # Cloudflare / challenge test (HTTP 403)
    resp_403 = MagicMock()
    resp_403.status_code = 403
    resp_403.text = "<html><body>Access Denied - verify you are human automated access challenge</body></html>"

    mock_session_403 = AsyncMock()
    mock_session_403.get = AsyncMock(return_value=resp_403)
    mock_session_403.__aenter__.return_value = mock_session_403
    mock_session_403.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session_403):
        with pytest.raises(BotDetectionEncountered):
            await agent._tier1_internal_api(
                product_name="Maybelline Kajal",
                brand="Maybelline",
                barcode="",
            )
