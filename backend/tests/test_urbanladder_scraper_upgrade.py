import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.services.agentic.scrapers.base_scraper import (
    BotDetectionEncountered,
    PlatformRateLimitError,
)
from app.services.agentic.scrapers.platform_scrapers import (
    UrbanLadderScraperAgent,
    PLATFORM_SCRAPERS,
)


@pytest.mark.asyncio
async def test_urbanladder_registered_in_platform_scrapers():
    assert "Urban Ladder" in PLATFORM_SCRAPERS
    assert isinstance(PLATFORM_SCRAPERS["Urban Ladder"], UrbanLadderScraperAgent)


@pytest.mark.asyncio
async def test_urbanladder_tier1_internal_api_success():
    agent = UrbanLadderScraperAgent()
    html_content = """
    <html>
      <body>
        <div class="xmdLL" data-testid="plp-product-card">
          <h2 class="XxwSy">
            <a data-testid="plp-product-card-title" href="/product/vetra-3-seater-leather-sofa-in-olive-9227440">
              Vetra 3 Seater Leather Sofa In Olive Colour
            </a>
          </h2>
          <div class="UYQNp">₹89,999</div>
          <div class="gc4ZJ">₹1,59,999</div>
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
            "Vetra 3 Seater Leather Sofa In Olive Colour", "Urban Ladder", ""
        )
        assert candidate is not None
        assert candidate["platform"] == "Urban Ladder"
        assert candidate["price"] == 89999.0
        assert candidate["mrp"] == 159999.0
        assert candidate["match_score"] == 1.0
        assert candidate["scrape_mode"] == "internal_api"
        assert "9227440" in candidate["product_url"]
        assert candidate["url_verified"] is True
        mock_session_cls.assert_called_once_with(impersonate="chrome124")


@pytest.mark.asyncio
async def test_urbanladder_tier1_internal_api_bot_detection_403():
    agent = UrbanLadderScraperAgent()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "<html><head><title>Access Denied</title></head><body><h1>Access Denied</h1></body></html>"

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        with pytest.raises(BotDetectionEncountered):
            await agent._tier1_internal_api(
                "Vetra 3 Seater Leather Sofa In Olive Colour", "Urban Ladder", ""
            )


def test_urbanladder_extract_cards_modern_card():
    agent = UrbanLadderScraperAgent()
    html_content = """
    <html>
      <body>
        <div class="xmdLL" data-testid="plp-product-card">
          <h2 class="XxwSy">
            <a data-testid="plp-product-card-title" href="/product/vetra-3-seater-leather-sofa-in-olive-9227440">
              Vetra 3 Seater Leather Sofa In Olive Colour
            </a>
          </h2>
          <div class="UYQNp">₹89,999</div>
          <div class="gc4ZJ">₹1,59,999</div>
        </div>
      </body>
    </html>
    """
    candidate = agent._extract_cards(
        html_content,
        "Vetra 3 Seater Leather Sofa In Olive Colour",
        "Urban Ladder",
        "",
        "https://www.urbanladder.com/products/search?keywords=sofa",
    )
    assert candidate is not None
    assert candidate["platform"] == "Urban Ladder"
    assert candidate["price"] == 89999.0
    assert candidate["mrp"] == 159999.0
    assert candidate["match_score"] == 1.0
    assert "9227440" in candidate["product_url"]
    assert candidate["url_verified"] is True


def test_urbanladder_extract_cards_legacy_selectors():
    agent = UrbanLadderScraperAgent()
    html_content = """
    <html>
      <body>
        <li class="product">
          <div class="productbox">
            <span class="name">Vetra 3 Seater Leather Sofa</span>
            <div class="price-number">
              <span>₹89,999</span>
            </div>
            <strike>₹1,59,999</strike>
            <a href="/products/vetra-sofa-legacy">View</a>
          </div>
        </li>
      </body>
    </html>
    """
    candidate = agent._extract_cards(
        html_content,
        "Vetra 3 Seater Leather Sofa",
        "",
        "",
        "https://www.urbanladder.com/products/search?keywords=sofa",
    )
    assert candidate is not None
    assert candidate["platform"] == "Urban Ladder"
    assert candidate["price"] == 89999.0
    assert candidate["mrp"] == 159999.0
    assert candidate["match_score"] == 1.0
    assert "vetra-sofa-legacy" in candidate["product_url"]
    assert candidate["url_verified"] is True
