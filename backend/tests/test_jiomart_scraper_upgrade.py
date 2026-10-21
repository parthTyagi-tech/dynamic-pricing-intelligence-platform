import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.agentic.scrapers.base_scraper import (
    BotDetectionEncountered,
    PlatformRateLimitError,
)
from app.services.agentic.scrapers.platform_scrapers import (
    JioMartScraperAgent,
    PLATFORM_SCRAPERS,
)


@pytest.mark.asyncio
async def test_jiomart_registered_in_platform_scrapers():
    assert "JioMart" in PLATFORM_SCRAPERS
    assert isinstance(PLATFORM_SCRAPERS["JioMart"], JioMartScraperAgent)


@pytest.mark.asyncio
async def test_tier1_internal_api_success():
    agent = JioMartScraperAgent()
    html_content = """
    <html>
      <body>
        <div class="ais-InfiniteHits-item">
          <div class="plp-card-details-name">Fortune Sunlite Refined Sunflower Oil 1 L</div>
          <span class="jm-heading-xxs">₹145.00</span>
          <span class="jm-body-xxs">₹175.00</span>
          <a href="/p/groceries/fortune-sunlite-oil/490000123">View</a>
        </div>
      </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_content

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session) as mock_session_cls:
        candidate = await agent._tier1_internal_api(
            "Fortune Sunlite Refined Sunflower Oil 1 L", "Fortune", ""
        )
        assert candidate is not None
        assert candidate["platform"] == "JioMart"
        assert candidate["price"] == 145.0
        assert candidate["mrp"] == 175.0
        assert candidate["match_score"] == 1.0
        assert candidate["scrape_mode"] == "internal_api"
        assert "490000123" in candidate["product_url"]
        assert candidate["url_verified"] is True

        # Verify session was instantiated with Mumbai cookies and chrome124 impersonation
        mock_session_cls.assert_called_once_with(
            impersonate="chrome124",
            cookies={
                "nms_mgo_pincode": "400020",
                "nms_mgo_city": "Mumbai",
                "nms_mgo_state_code": "MH",
            },
        )


@pytest.mark.asyncio
async def test_tier1_internal_api_bot_detection_403():
    agent = JioMartScraperAgent()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "<html><head><title>Access Denied</title></head><body><h1>Access Denied</h1></body></html>"

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        with pytest.raises(BotDetectionEncountered):
            await agent._tier1_internal_api(
                "Fortune Sunlite Refined Sunflower Oil 1 L", "Fortune", ""
            )


@pytest.mark.asyncio
async def test_tier3_playwright_algolia_xhr():
    agent = JioMartScraperAgent()

    registered_callbacks = []
    mock_page = AsyncMock()

    def mock_on(event, cb):
        if event == "response":
            registered_callbacks.append(cb)

    mock_page.on = MagicMock(side_effect=mock_on)

    async def mock_goto(url, **kwargs):
        # Trigger response callback simulating Algolia search response
        mock_resp = AsyncMock()
        mock_resp.url = "https://www.jiomart.com/api/v1/algolia/search"
        mock_resp.status = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "results": [
                {
                    "hits": [
                        {
                            "name": "Fortune Sunlite Refined Sunflower Oil 1 L",
                            "price": 145.0,
                            "mrp": 175.0,
                            "in_stock": True,
                            "url_path": "/p/groceries/fortune-sunlite-sunflower-oil-1-l/490000123",
                        }
                    ]
                }
            ]
        }
        for cb in registered_callbacks:
            await cb(mock_resp)

    mock_page.goto.side_effect = mock_goto
    mock_page.wait_for_selector = AsyncMock()
    mock_page.content.return_value = "<html></html>"

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page
    mock_context.add_cookies = AsyncMock()
    mock_context.add_init_script = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context
    mock_browser.close = AsyncMock()

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser
    mock_pw.stop = AsyncMock()

    mock_playwright_cm = AsyncMock()
    mock_playwright_cm.start.return_value = mock_pw

    with patch("playwright.async_api.async_playwright", return_value=mock_playwright_cm):
        candidate = await agent._tier3_playwright(
            task_id="task-123",
            product_id="prod-123",
            organization_id="org-123",
            product_name="Fortune Sunlite Refined Sunflower Oil 1 L",
            brand="Fortune",
            barcode="",
            catalog_price=175.0,
        )

        assert candidate is not None
        assert candidate["platform"] == "JioMart"
        assert candidate["price"] == 145.0
        assert candidate["mrp"] == 175.0
        assert candidate["match_score"] == 1.0
        assert candidate["scrape_mode"] == "playwright"
        assert "490000123" in candidate["product_url"]
        assert candidate["url_verified"] is True
        assert candidate["stock_status"] == "in_stock"


@pytest.mark.asyncio
async def test_tier3_playwright_dom_fallback():
    agent = JioMartScraperAgent()

    mock_page = AsyncMock()
    mock_page.on = MagicMock()
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.content.return_value = """
    <html>
      <body>
        <div class="ais-InfiniteHits-item">
          <div class="plp-card-details-name">Fortune Sunlite Refined Sunflower Oil 1 L</div>
          <span class="jm-heading-xxs">₹145.00</span>
          <span class="jm-body-xxs">₹175.00</span>
          <a href="/p/groceries/fortune-sunlite-oil/490000123">View</a>
        </div>
      </body>
    </html>
    """

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page
    mock_context.add_cookies = AsyncMock()
    mock_context.add_init_script = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context
    mock_browser.close = AsyncMock()

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser
    mock_pw.stop = AsyncMock()

    mock_playwright_cm = AsyncMock()
    mock_playwright_cm.start.return_value = mock_pw

    with patch("playwright.async_api.async_playwright", return_value=mock_playwright_cm):
        candidate = await agent._tier3_playwright(
            task_id="task-123",
            product_id="prod-123",
            organization_id="org-123",
            product_name="Fortune Sunlite Refined Sunflower Oil 1 L",
            brand="Fortune",
            barcode="",
            catalog_price=175.0,
        )

        assert candidate is not None
        assert candidate["platform"] == "JioMart"
        assert candidate["price"] == 145.0
        assert candidate["mrp"] == 175.0
        assert candidate["match_score"] == 1.0
        assert candidate["scrape_mode"] == "playwright"
        assert "490000123" in candidate["product_url"]
        assert candidate["url_verified"] is True
