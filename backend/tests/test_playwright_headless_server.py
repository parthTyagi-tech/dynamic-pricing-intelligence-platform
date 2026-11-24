import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.agentic.scrapers.base_scraper import BaseScraperAgent


@pytest.mark.asyncio
async def test_playwright_headless_server_launch_flags():
    """Verify Playwright is launched with proper headless flags for displayless servers."""
    scraper = BaseScraperAgent("TestPlatform", "https://example.com/search?q={query}", "https://example.com")

    mock_page = AsyncMock()
    mock_page.content.return_value = "<html><title>Test Product</title><body>â‚¹999.00</body></html>"
    mock_page.url = "https://example.com/product/123"

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_chromium = AsyncMock()
    mock_chromium.launch.return_value = mock_browser

    mock_pw = AsyncMock()
    mock_pw.chromium = mock_chromium

    mock_async_playwright = MagicMock()
    mock_async_playwright.return_value.start = AsyncMock(return_value=mock_pw)

    with patch("playwright.async_api.async_playwright", mock_async_playwright):
        with patch.object(scraper, "_invoke_extract_cards", return_value={"price": 999.0, "title": "Test Product"}):
            with patch.object(scraper, "_extract_structured_data", return_value=None):
                res = await scraper._tier3_playwright(
                    task_id="t1",
                    product_id="p1",
                    organization_id="o1",
                    product_name="Test Product",
                    brand="TestBrand",
                    barcode="",
                    catalog_price=1000.0,
                )

    # Verify launch arguments passed to Chromium
    mock_chromium.launch.assert_called_once()
    launch_kwargs = mock_chromium.launch.call_args.kwargs
    assert launch_kwargs.get("headless") is True
    args = launch_kwargs.get("args", [])
    assert "--headless=new" in args
    assert "--no-sandbox" in args
    assert "--disable-dev-shm-usage" in args
    assert "--disable-gpu" in args
    assert "--disable-setuid-sandbox" in args
    assert "--no-zygote" in args

    # Verify cleanup in finally:
    mock_browser.close.assert_called_once()
    mock_pw.stop.assert_called_once()


@pytest.mark.asyncio
async def test_playwright_missing_browser_binary_graceful_fallback():
    """Verify that if Playwright is installed but browser binaries are missing, it does not crash."""
    scraper = BaseScraperAgent("TestPlatform", "https://example.com/search?q={query}", "https://example.com")

    mock_chromium = AsyncMock()
    # Simulate missing Chromium executable
    mock_chromium.launch.side_effect = Exception(
        "Executable doesn't exist at /root/.cache/ms-playwright/chromium-1091/chrome-linux/chrome. Run \"playwright install\""
    )

    mock_pw = AsyncMock()
    mock_pw.chromium = mock_chromium

    mock_async_playwright = MagicMock()
    mock_async_playwright.return_value.start = AsyncMock(return_value=mock_pw)

    with patch("playwright.async_api.async_playwright", mock_async_playwright):
        # Should return None cleanly without raising an unhandled exception
        result = await scraper._tier3_playwright(
            task_id="t1",
            product_id="p1",
            organization_id="o1",
            product_name="Test Product",
            brand="TestBrand",
            barcode="",
            catalog_price=1000.0,
        )

    assert result is None
    # pw.stop() must still have been called in finally
    mock_pw.stop.assert_called_once()


@pytest.mark.asyncio
async def test_real_playwright_headless_execution():
    """Verify live headless browser can render a data URI without requiring a visual display."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        pytest.skip("Playwright not installed in environment")

    pw = await async_playwright().start()
    try:
        try:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ]
            )
        except Exception as launch_err:
            pytest.skip(f"Headless Chromium binary not installed or unavailable in this runner: {launch_err}")
            return

        page = await browser.new_page()
        await page.goto("data:text/html,<html><head><title>Server Render</title></head><body><h1>Price: Rs. 499</h1></body></html>")
        title = await page.title()
        content = await page.content()
        assert title == "Server Render"
        assert "Price: Rs. 499" in content
        await browser.close()
    finally:
        await pw.stop()
