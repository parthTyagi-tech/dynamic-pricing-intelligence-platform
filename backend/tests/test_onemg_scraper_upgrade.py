import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.agentic.scrapers.base_scraper import (
    BotDetectionEncountered,
    PlatformRateLimitError,
)
from app.services.agentic.scrapers.platform_scrapers import (
    OneMgScraperAgent,
    PLATFORM_SCRAPERS,
)


@pytest.mark.asyncio
async def test_onemg_registered_in_platform_scrapers():
    assert "1mg" in PLATFORM_SCRAPERS
    assert isinstance(PLATFORM_SCRAPERS["1mg"], OneMgScraperAgent)


@pytest.mark.asyncio
async def test_onemg_tier1_internal_api_json_success():
    agent = OneMgScraperAgent()
    mock_payload = {
        "data": {
            "search_results": [
                {
                    "name": "Dolo 650 Tablet",
                    "available": True,
                    "url": "/drugs/dolo-650-tablet-74467",
                    "prices": {
                        "discounted_price": "₹31",
                        "mrp": "₹32.28",
                    },
                }
            ]
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps(mock_payload)
    mock_resp.json.return_value = mock_payload

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session) as mock_session_cls:
        candidate = await agent._tier1_internal_api("Dolo 650 Tablet", "", "")
        assert candidate is not None
        assert candidate["platform"] == "1mg"
        assert candidate["price"] == 31.0
        assert candidate["mrp"] == 32.28
        assert candidate["match_score"] == 1.0
        assert candidate["scrape_mode"] == "internal_api"
        assert "74467" in candidate["product_url"]
        assert candidate["url_verified"] is True
        assert candidate["stock_status"] == "in_stock"
        mock_session_cls.assert_called_once_with(impersonate="chrome124")


@pytest.mark.asyncio
async def test_onemg_tier1_internal_api_preloaded_state_html():
    agent = OneMgScraperAgent()
    state_payload = {
        "searchReducer": {
            "searchResults": {
                "search_results": [
                    {
                        "name": "Dolo 650 Tablet",
                        "available": True,
                        "url": "/drugs/dolo-650-tablet-74467",
                        "prices": {
                            "discounted_price": 31.0,
                            "mrp": 32.28,
                        },
                    }
                ]
            }
        }
    }

    html_content = f"""
    <html>
      <head>
        <script>
          window.PRELOADED_STATE = {json.dumps(state_payload)};
        </script>
      </head>
      <body></body>
    </html>
    """

    mock_resp_api = MagicMock()
    mock_resp_api.status_code = 404
    mock_resp_api.text = "Not Found"

    mock_resp_html = MagicMock()
    mock_resp_html.status_code = 200
    mock_resp_html.text = html_content

    mock_session = AsyncMock()
    mock_session.get.side_effect = [
        mock_resp_api,   # pwa-dweb-api fails
        mock_resp_api,   # pharmacy_api_gateway fails
        mock_resp_html,  # search HTML succeeds
    ]
    mock_session.__aenter__.return_value = mock_session

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api("Dolo 650 Tablet", "", "")
        assert candidate is not None
        assert candidate["platform"] == "1mg"
        assert candidate["price"] == 31.0
        assert candidate["mrp"] == 32.28
        assert candidate["match_score"] == 1.0
        assert candidate["scrape_mode"] == "internal_api"
        assert "74467" in candidate["product_url"]


@pytest.mark.asyncio
async def test_onemg_tier1_internal_api_bot_detection_403():
    agent = OneMgScraperAgent()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "<html><head><title>Access Denied</title></head><body><h1>Access Denied</h1></body></html>"

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        with pytest.raises(BotDetectionEncountered):
            await agent._tier1_internal_api("Dolo 650 Tablet", "", "")


def test_onemg_extract_cards_wildcard_selectors():
    agent = OneMgScraperAgent()
    html_content = """
    <html>
      <body>
        <div class="style__product-box___p2raQ style__product-card___test">
          <div class="style__pro-title___2QwJy">Dolo 650 Tablet</div>
          <div class="style__price-tag___KzOkY">₹31.00</div>
          <span class="style__discount-price___25Bya">₹32.28</span>
          <a href="/drugs/dolo-650-tablet-74467">View</a>
        </div>
      </body>
    </html>
    """
    candidate = agent._extract_cards(
        html_content,
        "Dolo 650 Tablet",
        "",
        "",
        "https://www.1mg.com/search/all?name=Dolo",
    )
    assert candidate is not None
    assert candidate["platform"] == "1mg"
    assert candidate["price"] == 31.0
    assert candidate["mrp"] == 32.28
    assert candidate["match_score"] == 1.0
    assert "74467" in candidate["product_url"]
    assert candidate["url_verified"] is True
