import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.agentic.scrapers.platform_scrapers import NykaaScraperAgent, PurplleScraperAgent
from app.services.agentic.scrapers.base_scraper import BaseScraperAgent, ResilientSession, ResilientResponse

SAMPLE_NYKAA_HTML = """
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
              "title": "Maybelline New York The Colossal Kajal",
              "name": "Maybelline New York The Colossal Kajal",
              "price": 176.0,
              "mrp": 220.0,
              "slug": "maybelline-the-colossal-kajal/p/12153",
              "inStock": true
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

SAMPLE_PURPLLE_JSON = {
    "items": [
        {
            "id": "12345",
            "name": "Maybelline New York Colossal Kajal",
            "our_price": 175.0,
            "mrp": 220.0,
            "slug": "maybelline-colossal-kajal",
            "in_stock": True
        }
    ]
}


def _make_mock_aiohttp(status_code=200, text="", json_data=None):
    mock_resp = MagicMock()
    mock_resp.status = status_code
    mock_resp.text = AsyncMock(return_value=text)
    mock_resp.json = AsyncMock(return_value=json_data)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_resp
    mock_ctx.__aexit__.return_value = None

    mock_session = MagicMock()
    mock_session.get.return_value = mock_ctx
    mock_session.post.return_value = mock_ctx
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    return mock_session


@pytest.mark.asyncio
async def test_resilient_session_when_curl_cffi_missing():
    """Verify ResilientSession transparently falls back to aiohttp when curl_cffi is missing."""
    mock_aiohttp = _make_mock_aiohttp(200, "<html><body>Fallback OK</body></html>", {"status": "ok"})

    with patch("curl_cffi.requests.AsyncSession", side_effect=ModuleNotFoundError("No module named 'curl_cffi'")):
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp):
            async with ResilientSession() as session:
                resp = await session.get("https://example.com/test", timeout=10)
                assert resp.status_code == 200
                assert resp.text == "<html><body>Fallback OK</body></html>"
                assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_nykaa_tier1_fallback_when_curl_cffi_missing():
    """Verify Nykaa tier 1 gracefully uses aiohttp fallback when curl_cffi is missing."""
    agent = NykaaScraperAgent()
    mock_aiohttp = _make_mock_aiohttp(200, SAMPLE_NYKAA_HTML)

    with patch.dict("sys.modules", {"curl_cffi": None, "curl_cffi.requests": None}):
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp):
            candidate = await agent._tier1_internal_api(
                product_name="Maybelline New York The Colossal Kajal",
                brand="Maybelline",
                barcode="",
                catalog_price=180.0,
            )

    assert candidate is not None
    assert candidate["platform"] == "Nykaa"
    assert candidate["price"] == 176.0
    assert candidate["scrape_mode"] == "internal_api"


@pytest.mark.asyncio
async def test_purplle_tier1_fallback_when_curl_cffi_missing():
    """Verify Purplle tier 1 gracefully uses aiohttp fallback when curl_cffi is missing."""
    agent = PurplleScraperAgent()
    mock_aiohttp = _make_mock_aiohttp(200, json.dumps(SAMPLE_PURPLLE_JSON), SAMPLE_PURPLLE_JSON)

    with patch.dict("sys.modules", {"curl_cffi": None, "curl_cffi.requests": None}):
        with patch("aiohttp.ClientSession", return_value=mock_aiohttp):
            candidate = await agent._tier1_internal_api(
                product_name="Maybelline New York Colossal Kajal",
                brand="Maybelline",
                barcode="",
                catalog_price=180.0,
            )

    assert candidate is not None
    assert candidate["platform"] == "Purplle"
    assert candidate["price"] == 175.0
    assert candidate["scrape_mode"] == "internal_api"


@pytest.mark.asyncio
async def test_base_scraper_scrape_succeeds_without_curl_cffi():
    """Verify full end-to-end scraper scrape succeeds even if curl_cffi is completely missing."""
    agent = NykaaScraperAgent()
    mock_aiohttp = _make_mock_aiohttp(200, SAMPLE_NYKAA_HTML)

    product_dict = {
        "id": "prod-123",
        "name": "Maybelline New York The Colossal Kajal",
        "brand": "Maybelline",
        "barcode": "",
        "current_price": 180.0,
    }

    with patch.dict("os.environ", {"MOCK_SCRAPING": "false"}):
        with patch.dict("sys.modules", {"curl_cffi": None, "curl_cffi.requests": None}):
            with patch("aiohttp.ClientSession", return_value=mock_aiohttp):
                result = await agent.scrape(
                    task_id="test-task-no-curl-cffi",
                    product=product_dict,
                    organization_id="org-456",
                )

    assert result is not None
    assert result["platform"] == "Nykaa"
    assert result["price"] == 176.0
    assert result["scrape_mode"] == "internal_api"
