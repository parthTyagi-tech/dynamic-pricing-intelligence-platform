import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.agentic.scrapers.platform_scrapers import MeeshoScraperAgent
from app.services.agentic.scrapers.base_scraper import PlatformRateLimitError, BotDetectionEncountered

SAMPLE_API_JSON = {
    "catalogs": [
        {
            "id": 138107995,
            "product_id": "7i4a7z",
            "name": "Trendy Tshirts",
            "hero_product_name": "Urbane Modern Men Active Tshirts",
            "slug": "urbane-modern-men-active-tshirts",
            "min_catalog_price": 276.0,
            "min_product_price": 276.0,
            "mrp": 499.0,
            "valid": True
        }
    ]
}

SAMPLE_NEXT_DATA_HTML = """
<!DOCTYPE html>
<html>
<head>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "initialState": {
        "searchListing": {
          "listing": {
            "products": [
              {
                "id": "138107995",
                "product_id": "7i4a7z",
                "name": "Trendy Tshirts",
                "hero_product_name": "Urbane Modern Men Active Tshirts",
                "slug": "urbane-modern-men-active-tshirts",
                "min_catalog_price": 276.0,
                "min_product_price": 276.0,
                "mrp": 499.0
              }
            ]
          }
        }
      }
    }
  }
}
</script>
</head>
<body>
<div>Content</div>
</body>
</html>
"""

SAMPLE_DOM_HTML = """
<html>
<body>
  <div class="ProductList">
    <div class="ProductCard">
      <a href="/urbane-modern-men-active-tshirts/p/7i4a7z">
        <p class="CardTitle">Urbane Modern Men Active Tshirts</p>
        <h5 class="Price">₹276</h5>
        <span class="Mrp">₹499</span>
      </a>
    </div>
  </div>
</body>
</html>
"""

@pytest.mark.asyncio
async def test_meesho_tier1_internal_api_success():
    agent = MeeshoScraperAgent()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps(SAMPLE_API_JSON)
    mock_resp.json.return_value = SAMPLE_API_JSON

    mock_session = AsyncMock()
    mock_session.post = AsyncMock(return_value=mock_resp)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api(
            product_name="Urbane Modern Men Active Tshirts",
            brand="",
            barcode="",
            catalog_price=280.0,
        )

    assert candidate is not None
    assert candidate["platform"] == "Meesho"
    assert candidate["price"] == 276.0
    assert candidate["mrp"] == 499.0
    assert "Urbane Modern Men Active Tshirts" in candidate["product_title"]
    assert "urbane-modern-men-active-tshirts/p/7i4a7z" in candidate["product_url"]
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"
    assert candidate["scrape_mode"] == "internal_api"
    assert candidate["match_score"] >= 0.70

def test_meesho_extract_cards_next_data():
    agent = MeeshoScraperAgent()
    candidate = agent._extract_cards(
        html_text=SAMPLE_NEXT_DATA_HTML,
        target_name="Urbane Modern Men Active Tshirts",
        brand="",
        barcode="",
        search_url="https://www.meesho.com/search?q=tshirt",
        catalog_price=280.0,
    )

    assert candidate is not None
    assert candidate["platform"] == "Meesho"
    assert candidate["price"] == 276.0
    assert candidate["mrp"] == 499.0
    assert "7i4a7z" in candidate["product_url"]
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"
    assert candidate["scrape_mode"] == "mobile_headers"
    assert candidate["match_score"] >= 0.70

def test_meesho_extract_cards_dom_fallback():
    agent = MeeshoScraperAgent()
    candidate = agent._extract_cards(
        html_text=SAMPLE_DOM_HTML,
        target_name="Urbane Modern Men Active Tshirts",
        brand="",
        barcode="",
        search_url="https://www.meesho.com/search?q=tshirt",
        catalog_price=280.0,
    )

    assert candidate is not None
    assert candidate["platform"] == "Meesho"
    assert candidate["price"] == 276.0
    assert candidate["mrp"] == 499.0
    assert "Urbane Modern Men Active Tshirts" in candidate["product_title"]
    assert "7i4a7z" in candidate["product_url"]
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"
    assert candidate["scrape_mode"] == "mobile_headers"
    assert candidate["match_score"] >= 0.70

@pytest.mark.asyncio
async def test_meesho_catalog_price_ranking():
    agent = MeeshoScraperAgent()

    multi_catalog_json = {
        "catalogs": [
            {
                "id": 1,
                "product_id": "pid_expensive",
                "name": "Men Cotton Tshirts",
                "hero_product_name": "Men Cotton Tshirts 5-Pack Combo Set",
                "slug": "combo-pack-5",
                "min_catalog_price": 1499.0,
                "mrp": 2500.0,
            },
            {
                "id": 2,
                "product_id": "pid_target",
                "name": "Men Cotton Tshirts",
                "hero_product_name": "Men Cotton Tshirts Single Regular",
                "slug": "regular-tshirt",
                "min_catalog_price": 289.0,
                "mrp": 499.0,
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps(multi_catalog_json)
    mock_resp.json.return_value = multi_catalog_json

    mock_session = AsyncMock()
    mock_session.post = AsyncMock(return_value=mock_resp)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api(
            product_name="Men Cotton Tshirts",
            brand="",
            barcode="",
            catalog_price=300.0,
        )

    assert candidate is not None
    # Candidate closest to catalog_price 300.0 should be selected over 1499.0 combo
    assert candidate["price"] == 289.0

@pytest.mark.asyncio
async def test_meesho_bot_detection_and_rate_limit():
    agent = MeeshoScraperAgent()

    # Rate limit test (HTTP 429)
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.text = "Too Many Requests"

    mock_session_429 = AsyncMock()
    mock_session_429.post = AsyncMock(return_value=resp_429)
    mock_session_429.__aenter__.return_value = mock_session_429
    mock_session_429.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session_429):
        with pytest.raises(PlatformRateLimitError):
            await agent._tier1_internal_api(
                product_name="Cotton Kurti",
                brand="",
                barcode="",
            )

    # Bot challenge test (HTTP 403)
    resp_403 = MagicMock()
    resp_403.status_code = 403
    resp_403.text = "<html><body>Access Denied - verify you are human automated access challenge</body></html>"

    mock_session_403 = AsyncMock()
    mock_session_403.post = AsyncMock(return_value=resp_403)
    mock_session_403.__aenter__.return_value = mock_session_403
    mock_session_403.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session_403):
        with pytest.raises(BotDetectionEncountered):
            await agent._tier1_internal_api(
                product_name="Cotton Kurti",
                brand="",
                barcode="",
            )
