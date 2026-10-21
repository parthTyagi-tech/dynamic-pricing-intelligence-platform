import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.agentic.scrapers.platform_scrapers import AmazonScraperAgent


def test_extract_amazon_cards_filters_sponsored():
    html = """
    <html>
      <body>
        <!-- Sponsored card -->
        <div data-component-type="s-search-result" class="s-result-item AdHolder">
          <span class="puis-sponsored-label-text">Sponsored</span>
          <h2><span>Sony WH-1000XM5 Wireless Headphones (Sponsored)</span></h2>
          <span class="a-price"><span class="a-offscreen">&#8377;21,990</span></span>
        </div>
        <!-- Another sponsored card via badge -->
        <div data-component-type="s-search-result" class="s-result-item">
          <span class="s-sponsored-label-text">Sponsored</span>
          <h2><span>Sony WH-1000XM5 Wireless Headphones (Sponsored 2)</span></h2>
          <span class="a-price"><span class="a-offscreen">&#8377;22,990</span></span>
        </div>
        <!-- Organic card -->
        <div data-component-type="s-search-result" class="s-result-item" data-asin="B09XS7JWHH">
          <h2><span>Sony WH-1000XM5 Wireless Headphones</span></h2>
          <span class="s-price-instructions-style">
            <span class="a-price"><span class="a-offscreen">&#8377;24,990</span></span>
          </span>
        </div>
      </body>
    </html>
    """
    scraper = AmazonScraperAgent()
    candidate = scraper._extract_amazon_cards(
        html_text=html,
        target_name="Sony WH-1000XM5 Wireless Headphones",
        brand="Sony",
        barcode="",
        search_url="https://www.amazon.in/s?k=sony+wh-1000xm5"
    )
    assert candidate is not None
    assert candidate["price"] == 24990.0
    assert candidate["product_url"] == "https://www.amazon.in/dp/B09XS7JWHH"
    assert candidate["stock_status"] == "in_stock"
    assert candidate["in_stock"] is True
    assert "Sponsored" not in candidate["product_title"]


def test_extract_amazon_cards_price_whole_fallback():
    html = """
    <html>
      <body>
        <div data-component-type="s-search-result" class="s-result-item" data-asin="B07DJHXTLJ">
          <h2><span>Logitech M221 Wireless Mouse</span></h2>
          <div class="s-price-instructions-style">
            <span class="a-price-whole">1,299</span>
          </div>
        </div>
      </body>
    </html>
    """
    scraper = AmazonScraperAgent()
    candidate = scraper._extract_amazon_cards(
        html_text=html,
        target_name="Logitech M221 Wireless Mouse",
        brand="Logitech",
        barcode="",
        search_url="https://www.amazon.in/s?k=logitech+m221"
    )
    assert candidate is not None
    assert candidate["price"] == 1299.0
    assert candidate["product_url"] == "https://www.amazon.in/dp/B07DJHXTLJ"
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"


def test_extract_amazon_cards_data_asin_url_canonical():
    html = """
    <html>
      <body>
        <div data-component-type="s-search-result" class="s-result-item" data-asin="B08N5WRWNW">
          <div data-cy="title-recipe">
            <h2><span>Apple iPhone 15 128GB Black</span></h2>
          </div>
          <span class="a-price"><span class="a-offscreen">&#8377;71,999</span></span>
        </div>
      </body>
    </html>
    """
    scraper = AmazonScraperAgent()
    candidate = scraper._extract_amazon_cards(
        html_text=html,
        target_name="Apple iPhone 15 128GB Black",
        brand="Apple",
        barcode="",
        search_url="https://www.amazon.in/s?k=test"
    )
    assert candidate is not None
    assert candidate["product_url"] == "https://www.amazon.in/dp/B08N5WRWNW"
    assert candidate["url_verified"] is True
    assert candidate["price"] == 71999.0
    assert candidate["stock_status"] == "in_stock"


@pytest.mark.asyncio
async def test_tier1_internal_api_curl_cffi_success():
    sample_html = """
    <html>
      <body>
        <div data-component-type="s-search-result" class="s-result-item" data-asin="B0CHX1W1XY">
          <h2><span>Apple iPhone 15 128GB Black</span></h2>
          <span class="a-price"><span class="a-offscreen">&#8377;72,999</span></span>
        </div>
      </body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = sample_html

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session_cls = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", mock_session_cls):
        scraper = AmazonScraperAgent()
        candidate = await scraper._tier1_internal_api(
            product_name="Apple iPhone 15 128GB Black",
            brand="Apple",
            barcode=""
        )

    assert candidate is not None
    assert candidate["scrape_mode"] == "internal_api"
    assert candidate["price"] == 72999.0
    assert candidate["product_url"] == "https://www.amazon.in/dp/B0CHX1W1XY"

    # Verify impersonate was chrome124
    mock_session_cls.assert_called_with(impersonate="chrome124")
    # Verify headers contained en-IN
    call_args = mock_session.get.call_args
    headers = call_args[1]["headers"]
    assert "en-IN" in headers["Accept-Language"]


@pytest.mark.asyncio
async def test_tier1_internal_api_retry_on_relaxed_query():
    empty_html = "<html><body><div>No results found</div></body></html>"
    match_html = """
    <html>
      <body>
        <div data-component-type="s-search-result" class="s-result-item" data-asin="B0CHX1W1XY">
          <h2><span>Apple iPhone 15 128GB Black</span></h2>
          <span class="a-price"><span class="a-offscreen">&#8377;72,999</span></span>
        </div>
      </body>
    </html>
    """

    resp1 = MagicMock()
    resp1.status_code = 200
    resp1.text = empty_html

    resp2 = MagicMock()
    resp2.status_code = 200
    resp2.text = match_html

    mock_session = AsyncMock()
    mock_session.get.side_effect = [resp1, resp2]
    mock_session_cls = MagicMock(return_value=mock_session)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", mock_session_cls):
        scraper = AmazonScraperAgent()
        # Query with > 3 tokens: "Apple iPhone 15 128GB Black"
        candidate = await scraper._tier1_internal_api(
            product_name="Apple iPhone 15 128GB Black",
            brand="Apple",
            barcode=""
        )

    assert candidate is not None
    assert candidate["scrape_mode"] == "internal_api"
    assert candidate["price"] == 72999.0
    # Confirm get was called twice (first full query, then relaxed first 3 tokens)
    assert mock_session.get.call_count == 2
    second_url = mock_session.get.call_args_list[1][0][0]
    assert "Apple+iPhone+15" in second_url


@pytest.mark.asyncio
async def test_tier3_playwright_concurrency_and_wait():
    sample_html = """
    <html>
      <body>
        <div data-component-type="s-search-result" class="s-result-item" data-asin="B0CHX1W1XY">
          <h2><span>Apple iPhone 15 128GB Black</span></h2>
          <span class="a-price"><span class="a-offscreen">&#8377;74,999</span></span>
        </div>
      </body>
    </html>
    """

    mock_page = AsyncMock()
    mock_page.content.return_value = sample_html

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    mock_async_pw = MagicMock()
    mock_async_pw.return_value.start = AsyncMock(return_value=mock_pw)

    with patch("playwright.async_api.async_playwright", mock_async_pw):
        scraper = AmazonScraperAgent()
        candidate = await scraper._tier3_playwright(
            task_id="t1",
            product_id="p1",
            organization_id="o1",
            product_name="Apple iPhone 15 128GB Black",
            brand="Apple",
            barcode=""
        )

    assert candidate is not None
    assert candidate["scrape_mode"] == "playwright_stealth"
    assert candidate["price"] == 74999.0
    assert candidate["product_url"] == "https://www.amazon.in/dp/B0CHX1W1XY"

    # Verify wait_for_selector called with 8000ms timeout
    mock_page.wait_for_selector.assert_called_once_with(
        'div[data-component-type="s-search-result"]',
        timeout=8000
    )
    # Verify browser closed and pw stopped
    mock_browser.close.assert_called_once()
    mock_pw.stop.assert_called_once()
