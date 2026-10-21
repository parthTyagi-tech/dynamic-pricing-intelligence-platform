import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.agentic.scrapers.base_scraper import (
    BotDetectionEncountered,
    PlatformRateLimitError,
)
from app.services.agentic.scrapers.platform_scrapers import (
    BigBasketScraperAgent,
    PLATFORM_SCRAPERS,
)


@pytest.mark.asyncio
async def test_bigbasket_registered_in_platform_scrapers():
    assert "BigBasket" in PLATFORM_SCRAPERS
    assert isinstance(PLATFORM_SCRAPERS["BigBasket"], BigBasketScraperAgent)


@pytest.mark.asyncio
async def test_tier1_internal_api_bb2_success():
    agent = BigBasketScraperAgent()
    mock_payload = {
        "tabs": [
            {
                "product_info": {
                    "products": [
                        {
                            "desc": "Taaza Toned Milk",
                            "brand": {"name": "Amul"},
                            "pricing": {
                                "discount": {
                                    "prim_price": {"sp": "30.00"},
                                    "mrp": "32.00",
                                }
                            },
                            "id": "123456",
                            "slug": "amul-taaza-toned-milk",
                            "availability": {"is_in_stock": True},
                        }
                    ]
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps(mock_payload)
    mock_resp.json.return_value = mock_payload

    mock_session = AsyncMock()
    mock_session.get.side_effect = [
        MagicMock(status_code=200, text=""),  # bootstrap
        mock_resp,                            # listing API
    ]
    mock_session.__aenter__.return_value = mock_session

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api("Amul Taaza Toned Milk", "Amul", "")
        assert candidate is not None
        assert candidate["platform"] == "BigBasket"
        assert candidate["price"] == 30.0
        assert candidate["mrp"] == 32.0
        assert candidate["match_score"] == 1.0
        assert candidate["scrape_mode"] == "internal_api"
        assert "123456" in candidate["product_url"]
        assert candidate["url_verified"] is True
        assert candidate["stock_status"] == "in_stock"


@pytest.mark.asyncio
async def test_tier1_internal_api_legacy_tab_fallback():
    agent = BigBasketScraperAgent()
    mock_payload = {
        "tab": {
            "product_info": {
                "products": [
                    {
                        "p_desc": "Amul Taaza Toned Milk",
                        "sp": "30.00",
                        "mrp": "32.00",
                        "p_id": "99999",
                    }
                ]
            }
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = json.dumps(mock_payload)
    mock_resp.json.return_value = mock_payload

    mock_session = AsyncMock()
    mock_session.get.side_effect = [
        MagicMock(status_code=200, text=""),
        mock_resp,
    ]
    mock_session.__aenter__.return_value = mock_session

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api("Amul Taaza Toned Milk", "Amul", "")
        assert candidate is not None
        assert candidate["platform"] == "BigBasket"
        assert candidate["price"] == 30.0
        assert candidate["mrp"] == 32.0
        assert candidate["match_score"] == 1.0
        assert candidate["scrape_mode"] == "internal_api"
        assert "99999" in candidate["product_url"]


@pytest.mark.asyncio
async def test_tier1_internal_api_bot_detection_403():
    agent = BigBasketScraperAgent()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "<html><head><title>Access Denied</title></head><body><h1>Access Denied</h1></body></html>"

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        with pytest.raises(BotDetectionEncountered):
            await agent._tier1_internal_api("Amul Taaza Toned Milk", "Amul", "")


def test_extract_cards_next_data():
    agent = BigBasketScraperAgent()
    next_data = {
        "props": {
            "pageProps": {
                "initialData": {
                    "tabs": [
                        {
                            "product_info": {
                                "products": [
                                    {
                                        "desc": "Taaza Toned Milk",
                                        "brand": {"name": "Amul"},
                                        "pricing": {
                                            "discount": {
                                                "prim_price": {"sp": "30.00"},
                                                "mrp": "32.00",
                                            }
                                        },
                                        "id": "55512",
                                        "slug": "amul-taaza-toned-milk",
                                        "availability": {"is_in_stock": True},
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        }
    }
    html = f"""
    <html>
      <head>
        <script id="__NEXT_DATA__" type="application/json">
          {json.dumps(next_data)}
        </script>
      </head>
      <body></body>
    </html>
    """
    candidate = agent._extract_cards(html, "Amul Taaza Toned Milk", "Amul", "", "https://www.bigbasket.com/ps/?q=milk")
    assert candidate is not None
    assert candidate["platform"] == "BigBasket"
    assert candidate["price"] == 30.0
    assert candidate["mrp"] == 32.0
    assert candidate["match_score"] == 1.0
    assert "55512" in candidate["product_url"]


def test_extract_cards_dom_fallback():
    agent = BigBasketScraperAgent()
    html = """
    <html>
      <body>
        <div class="SKUDeck___StyledDiv">
          <h3 class="Label-sc">Amul Taaza Toned Milk</h3>
          <span class="Pricing___StyledLabel">₹30.00</span>
          <span class="Pricing___StyledLabel2">₹32.00</span>
          <a href="/pd/77788/amul-milk/">View</a>
        </div>
      </body>
    </html>
    """
    candidate = agent._extract_cards(html, "Amul Taaza Toned Milk", "Amul", "", "https://www.bigbasket.com/ps/?q=milk")
    assert candidate is not None
    assert candidate["platform"] == "BigBasket"
    assert candidate["price"] == 30.0
    assert candidate["mrp"] == 32.0
    assert candidate["match_score"] == 1.0
    assert "77788" in candidate["product_url"]
    assert candidate["url_verified"] is True
