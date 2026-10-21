import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.agentic.scrapers.platform_scrapers import AjioScraperAgent
from app.services.agentic.scrapers.base_scraper import PlatformRateLimitError, BotDetectionEncountered

SAMPLE_API_JSON = {
    "products": [
        {
            "code": "701094018_black",
            "name": "Essentials Small Logo Men's Tee",
            "fnlColorVariantData": {
                "brandName": "Puma",
                "colorGroup": "701094018_black"
            },
            "price": {
                "currencyIso": "INR",
                "value": 500.0
            },
            "wasPriceData": {
                "currencyIso": "INR",
                "value": 999.0
            },
            "url": "/puma-essentials-small-logo-men-s-tee/p/701094018_black"
        }
    ]
}

SAMPLE_PRELOADED_HTML = """
<!DOCTYPE html>
<html>
<head>
  <script>
    window.__PRELOADED_STATE__ = {
      "grid": {
        "entities": {
          "701094018001": {
            "code": "701094018_black",
            "name": "Essentials Small Logo Men's Tee",
            "fnlColorVariantData": {
              "brandName": "Puma"
            },
            "price": {
              "value": 500.0
            },
            "wasPriceData": {
              "value": 999.0
            },
            "url": "/puma-essentials-small-logo-men-s-tee/p/701094018_black"
          }
        }
      }
    };
  </script>
</head>
<body>
  <div>Grid Content</div>
</body>
</html>
"""

SAMPLE_DOM_HTML = """
<html>
<body>
  <div class="items">
    <div class="item">
      <a href="/puma-essentials-small-logo-men-s-tee/p/701094018_black">
        <div class="contentHolder">
          <div class="brand">Puma</div>
          <div class="nameCls">Essentials Small Logo Men's Tee</div>
          <div class="price">
            <span class="price">Rs. 500</span>
            <span class="orginal-price">Rs. 999</span>
          </div>
        </div>
      </a>
    </div>
  </div>
</body>
</html>
"""

@pytest.mark.asyncio
async def test_ajio_tier1_internal_api_success():
    agent = AjioScraperAgent()

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
            product_name="Puma Essentials Small Logo Men's Tee",
            brand="Puma",
            barcode="",
            catalog_price=500.0,
        )

    assert candidate is not None
    assert candidate["platform"] == "Ajio"
    assert candidate["price"] == 500.0
    assert candidate["mrp"] == 999.0
    assert "Puma" in candidate["product_title"]
    assert "701094018_black" in candidate["product_url"]
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"
    assert candidate["scrape_mode"] == "internal_api"
    assert candidate["match_score"] >= 0.70

def test_ajio_extract_cards_preloaded_state():
    agent = AjioScraperAgent()
    candidate = agent._extract_cards(
        html_text=SAMPLE_PRELOADED_HTML,
        target_name="Puma Essentials Small Logo Men's Tee",
        brand="Puma",
        barcode="",
        search_url="https://www.ajio.com/search/?text=Puma+Tee",
        catalog_price=500.0,
    )

    assert candidate is not None
    assert candidate["platform"] == "Ajio"
    assert candidate["price"] == 500.0
    assert candidate["mrp"] == 999.0
    assert "701094018_black" in candidate["product_url"]
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"
    assert candidate["scrape_mode"] == "mobile_headers"
    assert candidate["match_score"] >= 0.70

def test_ajio_extract_cards_dom_fallback():
    agent = AjioScraperAgent()
    candidate = agent._extract_cards(
        html_text=SAMPLE_DOM_HTML,
        target_name="Puma Essentials Small Logo Men's Tee",
        brand="Puma",
        barcode="",
        search_url="https://www.ajio.com/search/?text=Puma+Tee",
        catalog_price=500.0,
    )

    assert candidate is not None
    assert candidate["platform"] == "Ajio"
    assert candidate["price"] == 500.0
    assert candidate["mrp"] == 999.0
    assert "Puma" in candidate["product_title"]
    assert "701094018_black" in candidate["product_url"]
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"
    assert candidate["scrape_mode"] == "mobile_headers"
    assert candidate["match_score"] >= 0.70

@pytest.mark.asyncio
async def test_ajio_catalog_price_ranking():
    agent = AjioScraperAgent()

    multi_product_json = {
        "products": [
            {
                "code": "p1_expensive",
                "name": "Puma Men Tee Jacket Combo",
                "fnlColorVariantData": {"brandName": "Puma"},
                "price": {"value": 4500.0},
                "wasPriceData": {"value": 6000.0},
                "url": "/combo/p/1"
            },
            {
                "code": "p2_target",
                "name": "Puma Men Tee Regular",
                "fnlColorVariantData": {"brandName": "Puma"},
                "price": {"value": 520.0},
                "wasPriceData": {"value": 999.0},
                "url": "/tee/p/2"
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps(multi_product_json)
    mock_resp.json.return_value = multi_product_json

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_resp)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api(
            product_name="Puma Men Tee",
            brand="Puma",
            barcode="",
            catalog_price=500.0,
        )

    assert candidate is not None
    # Candidate closest to 500.0 should be selected over the 4500.0 outlier
    assert candidate["price"] == 520.0

@pytest.mark.asyncio
async def test_ajio_bot_detection_and_rate_limit():
    agent = AjioScraperAgent()

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
                product_name="Puma Men Tee",
                brand="Puma",
                barcode="",
            )

    # Cloudflare/Akamai challenge test (HTTP 403)
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
                product_name="Puma Men Tee",
                brand="Puma",
                barcode="",
            )
