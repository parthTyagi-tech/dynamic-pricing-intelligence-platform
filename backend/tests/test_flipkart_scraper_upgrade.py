import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.agentic.scrapers.platform_scrapers import FlipkartScraperAgent


def test_extract_from_initial_state_success():
    state_payload = {
        "pageDataV4": {
            "page": {
                "data": {
                    "10003": [
                        {
                            "slotType": "WIDGET",
                            "widget": {
                                "type": "PRODUCT_SUMMARY",
                                "data": {
                                    "products": [
                                        {
                                            "productInfo": {
                                                "value": {
                                                    "titles": {
                                                        "newTitle": "boAt BassHeads 100 Wired Earphones Wired Headset",
                                                        "title": "boAt BassHeads 100 Wired Earphones",
                                                    },
                                                    "pricing": {
                                                        "finalPrice": {"value": 349},
                                                        "mrp": {"value": 999},
                                                    },
                                                    "baseUrl": "/boat-bassheads-100-wired-earphones/p/itm3f39544d0b96c?pid=ACCEVQZABYWJHRHF",
                                                }
                                            }
                                        }
                                    ]
                                }
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
        <script>window.__INITIAL_STATE__ = {json.dumps(state_payload)};</script>
      </head>
      <body></body>
    </html>
    """

    agent = FlipkartScraperAgent()
    candidate = agent._extract_from_initial_state(
        html_text=html,
        target_name="boAt BassHeads 100 Wired Earphones",
        brand="boAt",
        barcode="",
        search_url="https://www.flipkart.com/search?q=boat+bassheads+100",
        catalog_price=399.0,
    )

    assert candidate is not None
    assert candidate["platform"] == "Flipkart"
    assert candidate["price"] == 349.0
    assert candidate["mrp"] == 999.0
    assert candidate["stock_status"] == "in_stock"
    assert candidate["in_stock"] is True
    assert candidate["url_verified"] is True
    assert "itm3f39544d0b96c" in candidate["product_url"]
    assert candidate["product_url"].startswith("https://www.flipkart.com/boat-bassheads-100-wired-earphones/p/itm3f39544d0b96c")
    assert "?" not in candidate["product_url"]


def test_extract_flipkart_cards_dom_selectors():
    html = """
    <html>
      <body>
        <div class="cPHDOP col-12-12">
          <div class="_4ddWXP" data-id="HEADSET123">
            <a class="wjcEIp" href="/boat-bassheads-100-wired/p/itmfk12345?pid=ACCEVQZ">
              <div class="KzDlHZ">boAt BassHeads 100 Wired Earphones</div>
            </a>
            <div class="Nx9bqj">₹349</div>
            <div class="yRaY8j">₹999</div>
          </div>
        </div>
      </body>
    </html>
    """
    agent = FlipkartScraperAgent()
    candidate = agent._extract_flipkart_cards(
        html_text=html,
        target_name="boAt BassHeads 100 Wired Earphones",
        brand="boAt",
        barcode="",
        search_url="https://www.flipkart.com/search?q=boat+bassheads+100",
        catalog_price=399.0,
    )

    assert candidate is not None
    assert candidate["price"] == 349.0
    assert candidate["mrp"] == 999.0
    assert candidate["stock_status"] == "in_stock"
    assert candidate["in_stock"] is True
    assert candidate["product_url"] == "https://www.flipkart.com/boat-bassheads-100-wired/p/itmfk12345"
    assert candidate["url_verified"] is True


def test_extract_flipkart_cards_price_regex_fallback():
    html = """
    <html>
      <body>
        <div class="slAVV4" data-id="HEADSET999">
          <div class="_4rR01T">boAt BassHeads 100 Wired Earphones</div>
          <div>Special Price: Rs. 389 only</div>
          <a href="/boat-bassheads-100-wired/p/itmfk99999?pid=XYZ">View Details</a>
        </div>
      </body>
    </html>
    """
    agent = FlipkartScraperAgent()
    candidate = agent._extract_flipkart_cards(
        html_text=html,
        target_name="boAt BassHeads 100 Wired Earphones",
        brand="boAt",
        barcode="",
        search_url="https://www.flipkart.com/search?q=test",
    )

    assert candidate is not None
    assert candidate["price"] == 389.0
    assert candidate["stock_status"] == "in_stock"
    assert "itmfk99999" in candidate["product_url"]


@pytest.mark.asyncio
async def test_tier1_internal_api_curl_cffi_success():
    state_payload = {
        "pageDataV4": {
            "page": {
                "data": {
                    "10003": [
                        {
                            "widget": {
                                "type": "PRODUCT_SUMMARY",
                                "data": {
                                    "products": [
                                        {
                                            "productInfo": {
                                                "value": {
                                                    "titles": {"newTitle": "boAt BassHeads 100 Wired Earphones"},
                                                    "pricing": {"finalPrice": {"value": 349}},
                                                    "baseUrl": "/boat-bassheads-100/p/itmlive123",
                                                }
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    ]
                }
            }
        }
    }
    sample_html = f"<html><script>window.__INITIAL_STATE__ = {json.dumps(state_payload)};</script></html>"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = sample_html

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session_cls = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", mock_session_cls):
        agent = FlipkartScraperAgent()
        candidate = await agent._tier1_internal_api(
            product_name="boAt BassHeads 100 Wired Earphones",
            brand="boAt",
            barcode="",
        )

    assert candidate is not None
    assert candidate["scrape_mode"] == "internal_api"
    assert candidate["price"] == 349.0
    assert "itmlive123" in candidate["product_url"]

    # Verify desktop Chrome 124 headers and impersonation
    mock_session_cls.assert_called_with(impersonate="chrome124")
    call_args = mock_session.get.call_args
    headers = call_args[1]["headers"]
    assert "Windows NT 10.0" in headers["User-Agent"]
    assert "en-IN" in headers["Accept-Language"]


@pytest.mark.asyncio
async def test_tier1_internal_api_fallback_to_dom():
    dom_html = """
    <html>
      <body>
        <div class="tUxRFH">
          <div class="KzDlHZ">boAt BassHeads 100 Wired Earphones</div>
          <div class="Nx9bqj">₹349</div>
          <a href="/boat-bassheads-100/p/itmdom456">Link</a>
        </div>
      </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = dom_html

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session_cls = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", mock_session_cls):
        agent = FlipkartScraperAgent()
        candidate = await agent._tier1_internal_api(
            product_name="boAt BassHeads 100 Wired Earphones",
            brand="boAt",
            barcode="",
        )

    assert candidate is not None
    assert candidate["scrape_mode"] == "internal_api"
    assert candidate["price"] == 349.0
    assert "itmdom456" in candidate["product_url"]


@pytest.mark.asyncio
async def test_tier3_playwright_semaphore_concurrency():
    sample_html = """
    <html>
      <body>
        <div class="tUxRFH">
          <div class="KzDlHZ">boAt BassHeads 100 Wired Earphones</div>
          <div class="Nx9bqj">₹349</div>
          <a href="/boat-bassheads-100/p/itmpw789">Link</a>
        </div>
      </body>
    </html>
    """

    mock_btn = AsyncMock()
    mock_btn.is_visible.return_value = False

    mock_locator = MagicMock()
    mock_locator.first = mock_btn
    mock_locator.first.wait_for = AsyncMock()

    mock_page = AsyncMock()
    mock_page.content.return_value = sample_html
    mock_page.locator.return_value = mock_locator
    mock_page.keyboard = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_async_pw = MagicMock()
    mock_async_pw.return_value.start = AsyncMock(return_value=mock_pw)

    with patch("playwright.async_api.async_playwright", mock_async_pw):
        agent = FlipkartScraperAgent()
        candidate = await agent._tier3_playwright(
            task_id="t1",
            product_id="p1",
            organization_id="o1",
            product_name="boAt BassHeads 100 Wired Earphones",
            brand="boAt",
            barcode="",
        )

    assert candidate is not None
    assert candidate["scrape_mode"] == "playwright_stealth"
    assert candidate["price"] == 349.0
    assert "itmpw789" in candidate["product_url"]

    mock_browser.close.assert_called_once()
    mock_pw.stop.assert_called_once()
