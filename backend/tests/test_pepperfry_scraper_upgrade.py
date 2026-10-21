import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.agentic.scrapers.base_scraper import (
    BotDetectionEncountered,
    PlatformRateLimitError,
)
from app.services.agentic.scrapers.platform_scrapers import (
    PepperfryScraperAgent,
    PLATFORM_SCRAPERS,
)


@pytest.mark.asyncio
async def test_pepperfry_registered_in_platform_scrapers():
    assert "Pepperfry" in PLATFORM_SCRAPERS
    assert isinstance(PLATFORM_SCRAPERS["Pepperfry"], PepperfryScraperAgent)


@pytest.mark.asyncio
async def test_pepperfry_tier1_internal_api_success():
    agent = PepperfryScraperAgent()
    html_content = """
    <html>
      <body>
        <pf-clip-product-card>
          <div class="product-details">
            <h2 class="product-name">Yukio Breathable Mesh Ergonomic Chair</h2>
            <div class="product-brand">Mintwud</div>
          </div>
          <div class="product-price">
            <span class="product-offer-price">₹3,299</span>
            <span class="product-mrp-price">₹7,499</span>
          </div>
          <a href="/product/yukio-breathable-mesh-chair-2226053.html">View</a>
        </pf-clip-product-card>
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
            "Yukio Breathable Mesh Ergonomic Chair", "Mintwud", ""
        )
        assert candidate is not None
        assert candidate["platform"] == "Pepperfry"
        assert candidate["price"] == 3299.0
        assert candidate["mrp"] == 7499.0
        assert candidate["match_score"] == 1.0
        assert candidate["scrape_mode"] == "internal_api"
        assert "2226053" in candidate["product_url"]
        assert candidate["url_verified"] is True
        mock_session_cls.assert_called_once_with(impersonate="chrome124")


@pytest.mark.asyncio
async def test_pepperfry_tier1_internal_api_bot_detection_403():
    agent = PepperfryScraperAgent()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "<html><head><title>Access Denied</title></head><body><h1>Access Denied</h1></body></html>"

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        with pytest.raises(BotDetectionEncountered):
            await agent._tier1_internal_api(
                "Yukio Breathable Mesh Ergonomic Chair", "Mintwud", ""
            )


def test_pepperfry_extract_cards_pf_clip_product_card():
    agent = PepperfryScraperAgent()
    html_content = """
    <html>
      <body>
        <pf-clip-product-card>
          <div class="product-details">
            <h2 class="product-name">Yukio Breathable Mesh Ergonomic Chair</h2>
            <div class="product-brand">Mintwud</div>
          </div>
          <div class="product-price">
            <span class="product-offer-price">₹3,299</span>
            <span class="product-mrp-price">₹7,499</span>
          </div>
          <a href="/product/yukio-breathable-mesh-chair-2226053.html">View</a>
        </pf-clip-product-card>
      </body>
    </html>
    """
    candidate = agent._extract_cards(
        html_content,
        "Yukio Breathable Mesh Ergonomic Chair",
        "Mintwud",
        "",
        "https://www.pepperfry.com/site_product/search?q=chair",
    )
    assert candidate is not None
    assert candidate["platform"] == "Pepperfry"
    assert candidate["price"] == 3299.0
    assert candidate["mrp"] == 7499.0
    assert candidate["match_score"] == 1.0
    assert "2226053" in candidate["product_url"]
    assert candidate["url_verified"] is True


def test_pepperfry_extract_cards_legacy_clipCard():
    agent = PepperfryScraperAgent()
    html_content = """
    <html>
      <body>
        <div class="clipCard">
          <span class="clipCard__brand">Mintwud</span>
          <h2 class="clipCard__title">Yukio Breathable Mesh Ergonomic Chair</h2>
          <span class="clipCard__price--bold">₹3,299</span>
          <span class="clipCard__mrp">₹7,499</span>
          <a class="clipCard__galleryWrap" href="/product/yukio-chair-legacy.html">View</a>
        </div>
      </body>
    </html>
    """
    candidate = agent._extract_cards(
        html_content,
        "Yukio Breathable Mesh Ergonomic Chair",
        "Mintwud",
        "",
        "https://www.pepperfry.com/site_product/search?q=chair",
    )
    assert candidate is not None
    assert candidate["platform"] == "Pepperfry"
    assert candidate["price"] == 3299.0
    assert candidate["mrp"] == 7499.0
    assert candidate["match_score"] >= 0.8
    assert "yukio-chair-legacy" in candidate["product_url"]
    assert candidate["url_verified"] is True
