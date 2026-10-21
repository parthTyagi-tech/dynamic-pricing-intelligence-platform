import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import quote_plus
from app.services.agentic.scrapers.platform_scrapers import CromaScraperAgent


def test_extract_croma_from_json_highest_scoring():
    api_payload = {
        "products": [
            {
                "name": "Case Cover for Sony WH-1000XM5 Headphones",
                "price": {"value": 1499.0},
                "mrp": {"value": 2999.0},
                "url": "/case-cover-sony-wh-1000xm5/p/999999",
                "stockFlag": ["STORE-1"],
            },
            {
                "name": "SONY WH-1000XM5 Bluetooth Headphone with Mic (Auto Noise Cancelling Optimizer, Over Ear, Black)",
                "price": {"value": 19989.0},
                "mrp": {"value": 34990.0},
                "url": "/sony-wh-1000xm5-bluetooth-headphone-with-mic-auto-noise-cancellation-optimizer-over-ear-black-/p/262565",
                "stockFlag": ["STORE-1", "STORE-2"],
            },
        ]
    }

    agent = CromaScraperAgent()
    candidate = agent._extract_croma_from_json(
        data=api_payload,
        product_name="Sony WH-1000XM5 Noise Cancelling Headphones",
        brand="Sony",
        barcode="",
        search_url="https://www.croma.com/searchB?q=Sony+WH-1000XM5",
        catalog_price=24990.0,
    )

    assert candidate is not None
    assert candidate["platform"] == "Croma"
    assert candidate["price"] == 19989.0
    assert candidate["mrp"] == 34990.0
    assert candidate["stock_status"] == "in_stock"
    assert candidate["in_stock"] is True
    assert candidate["url_verified"] is True
    assert "262565" in candidate["product_url"]
    assert "Case Cover" not in candidate["product_title"]
    assert candidate["match_score"] >= 0.85


@pytest.mark.asyncio
async def test_tier1_internal_api_curl_cffi_success():
    api_payload = {
        "products": [
            {
                "name": "Sony WH-1000XM5 Noise Cancelling Headphones",
                "price": {"value": 19989.0},
                "mrp": {"value": 34990.0},
                "url": "/sony-wh-1000xm5/p/262565",
                "stockFlag": ["STORE-1"],
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "{\"products\": []}"
    mock_resp.json.return_value = api_payload

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session_cls = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", mock_session_cls):
        agent = CromaScraperAgent()
        candidate = await agent._tier1_internal_api(
            product_name="Sony WH-1000XM5 Noise Cancelling Headphones",
            brand="Sony",
            barcode="",
        )

    assert candidate is not None
    assert candidate["scrape_mode"] == "internal_api"
    assert candidate["price"] == 19989.0
    assert candidate["product_url"] == "https://www.croma.com/sony-wh-1000xm5/p/262565"

    # Verify Chrome 124 impersonation and headers
    mock_session_cls.assert_called_with(impersonate="chrome124")
    call_args = mock_session.get.call_args
    called_url = call_args[0][0]
    headers = call_args[1]["headers"]
    assert "searchservices/v1/search" in called_url
    assert "channelCode=400049" in called_url
    assert headers["csc-channel"] == "WEB"
    assert headers["Origin"] == "https://www.croma.com"


@pytest.mark.asyncio
async def test_tier3_playwright_semaphore_and_response_interception():
    intercepted_payload = {
        "products": [
            {
                "name": "Sony WH-1000XM5 Noise Cancelling Headphones",
                "price": {"value": 19989.0},
                "mrp": {"value": 34990.0},
                "url": "/sony-wh-1000xm5/p/262565",
                "stockFlag": ["STORE-1"],
            }
        ]
    }

    class FakeResponse:
        url = "https://api.croma.com/searchservices/v1/search?query=test"
        status = 200
        headers = {"content-type": "application/json;charset=utf-8"}
        async def json(self):
            return intercepted_payload

    listeners = {}
    mock_page = MagicMock()
    mock_page.content = AsyncMock(return_value="<html><body></body></html>")
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.route = AsyncMock()
    def fake_on(evt, handler):
        listeners[evt] = handler
    mock_page.on = MagicMock(side_effect=fake_on)

    async def fake_goto(url, **kwargs):
        if "response" in listeners:
            res = listeners["response"](FakeResponse())
            if asyncio.iscoroutine(res):
                await res
    mock_page.goto = AsyncMock(side_effect=fake_goto)

    mock_context = MagicMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.add_init_script = AsyncMock()

    mock_browser = MagicMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_pw = MagicMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_pw.stop = AsyncMock()

    mock_async_pw = MagicMock()
    mock_async_pw.return_value.start = AsyncMock(return_value=mock_pw)

    with patch("playwright.async_api.async_playwright", mock_async_pw):
        agent = CromaScraperAgent()
        candidate = await agent._tier3_playwright(
            task_id="t1",
            product_id="p1",
            organization_id="o1",
            product_name="Sony WH-1000XM5 Noise Cancelling Headphones",
            brand="Sony",
            barcode="",
        )

    assert candidate is not None
    assert candidate["scrape_mode"] == "playwright_stealth"
    assert candidate["price"] == 19989.0
    assert "262565" in candidate["product_url"]

    mock_browser.close.assert_called_once()
    mock_pw.stop.assert_called_once()


def test_extract_croma_cards_dom_fallback():
    dom_html = """
    <html>
      <body>
        <ul class="product-list">
          <li class="product-item">
            <h3 class="product-title">
              <a href="/sony-wh-1000xm5-headphones/p/262565">Sony WH-1000XM5 Noise Cancelling Headphones</a>
            </h3>
            <span class="amount">₹19,989</span>
            <span class="old-price">₹34,990</span>
          </li>
        </ul>
      </body>
    </html>
    """
    agent = CromaScraperAgent()
    candidate = agent._extract_croma_cards(
        html_text=dom_html,
        target_name="Sony WH-1000XM5 Noise Cancelling Headphones",
        brand="Sony",
        barcode="",
        search_url="https://www.croma.com/searchB?q=test",
    )

    assert candidate is not None
    assert candidate["price"] == 19989.0
    assert candidate["mrp"] == 34990.0
    assert candidate["stock_status"] == "in_stock"
    assert "262565" in candidate["product_url"]
