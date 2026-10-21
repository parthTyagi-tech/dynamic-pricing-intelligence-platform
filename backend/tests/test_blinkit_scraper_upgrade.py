import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.agentic.scrapers.base_scraper import (
    BotDetectionEncountered,
    PlatformRateLimitError,
)
from app.services.agentic.scrapers.platform_scrapers import (
    BlinkitScraperAgent,
    PLATFORM_SCRAPERS,
)


@pytest.mark.asyncio
async def test_blinkit_headers_contract():
    agent = BlinkitScraperAgent()
    assert hasattr(agent, "headers"), "BlinkitScraperAgent must define self.headers"
    assert agent.headers.get("lat") == "28.6139", "Blinkit lat header must be 28.6139 (Delhi)"
    assert agent.headers.get("lon") == "77.2090", "Blinkit lon header must be 77.2090 (Delhi)"
    assert agent.headers.get("app_client") == "consumer_web"
    assert "Chrome/124" in agent.headers.get("User-Agent", "")


@pytest.mark.asyncio
async def test_playwright_e2e_verification_check_compliance():
    """Directly mirror check 3.2 in tools/playwright_e2e_verification.py."""
    b_inst = PLATFORM_SCRAPERS.get("Blinkit")
    assert b_inst is not None, "Blinkit must be in PLATFORM_SCRAPERS"
    b_headers = getattr(b_inst, "headers", {})
    assert b_headers.get("lat") == "28.6139", f"lat was {b_headers.get('lat')}"
    assert b_headers.get("lon") == "77.2090", f"lon was {b_headers.get('lon')}"


@pytest.mark.asyncio
async def test_tier1_internal_api_success():
    agent = BlinkitScraperAgent()
    mock_payload = {
        "response": {
            "snippets": [
                {
                    "data": {
                        "name": {"text": "Amul Taaza Toned Milk"},
                        "normal_price": {"text": "₹30"},
                        "mrp": {"text": "₹32"},
                        "product_id": "19512",
                        "is_sold_out": False,
                    }
                }
            ]
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "{}"
    mock_resp.json.return_value = mock_payload

    mock_session = AsyncMock()
    mock_session.get.return_value = MagicMock(status_code=200, text="")
    mock_session.post.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api("Amul Taaza Toned Milk", "Amul", "")
        assert candidate is not None
        assert candidate["platform"] == "Blinkit"
        assert candidate["price"] == 30.0
        assert candidate["mrp"] == 32.0
        assert candidate["match_score"] == 1.0
        assert candidate["scrape_mode"] == "internal_api"
        assert "19512" in candidate["product_url"]
        assert candidate["url_verified"] is True
        assert candidate["stock_status"] == "in_stock"


@pytest.mark.asyncio
async def test_tier1_internal_api_cloudflare_challenge_escalates():
    agent = BlinkitScraperAgent()
    cf_resp = MagicMock()
    cf_resp.status_code = 403
    cf_resp.text = "<html><title>Just a moment...</title>Cloudflare challenge cf-mitigated: challenge</html>"

    mock_session = AsyncMock()
    mock_session.get.return_value = cf_resp
    mock_session.post.return_value = cf_resp
    mock_session.__aenter__.return_value = mock_session

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        with pytest.raises(BotDetectionEncountered):
            await agent._tier1_internal_api("Amul Taaza Toned Milk", "Amul", "")


@pytest.mark.asyncio
async def test_tier3_playwright_semaphore_and_geolocation():
    agent = BlinkitScraperAgent()
    mock_sem = AsyncMock()
    mock_sem.__aenter__.return_value = None
    mock_sem.__aexit__.return_value = None

    mock_page = AsyncMock()
    mock_page.on = MagicMock()
    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page
    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context
    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    with patch("app.services.agentic.scrapers.platform_scrapers._get_playwright_semaphore", return_value=mock_sem), \
         patch("playwright.async_api.async_playwright") as mock_pw_factory:
        mock_pw_factory.return_value.start = AsyncMock(return_value=mock_pw)

        await agent._tier3_playwright(
            task_id="task-1",
            product_id="prod-1",
            organization_id="org-1",
            product_name="Amul Taaza Toned Milk",
            brand="Amul",
            barcode="",
            catalog_price=30.0,
        )

        mock_sem.__aenter__.assert_awaited_once()
        mock_browser.new_context.assert_called_once()
        _, kwargs = mock_browser.new_context.call_args
        assert kwargs.get("geolocation") == {"latitude": 28.6139, "longitude": 77.2090}
        assert "geolocation" in kwargs.get("permissions", [])
        assert kwargs.get("locale") == "en-IN"
