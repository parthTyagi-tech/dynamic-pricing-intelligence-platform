import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.agentic.scrapers.platform_scrapers import ScoobooScraperAgent

SAMPLE_SUGGEST_JSON = {
    "resources": {
        "results": {
            "products": [
                {
                    "id": 6966869852215,
                    "title": "Tombow Airpress Pressurized Ballpoint Pen",
                    "handle": "tombow-airpress-pressurized-ballpoint-pen",
                    "price": "671.78",
                    "compare_at_price": "1590.00",
                    "available": True,
                    "url": "/products/tombow-airpress-pressurized-ballpoint-pen",
                },
                {
                    "id": 6966869852216,
                    "title": "Tombow Airpress Ballpoint Pen Refill Black",
                    "handle": "tombow-airpress-ballpoint-pen-refill-black",
                    "price": "150.00",
                    "compare_at_price": "200.00",
                    "available": True,
                    "url": "/products/tombow-airpress-ballpoint-pen-refill-black",
                }
            ]
        }
    }
}

SAMPLE_DETAIL_JSON = {
    "product": {
        "id": 6966869852215,
        "title": "Tombow Airpress Pressurized Ballpoint Pen",
        "handle": "tombow-airpress-pressurized-ballpoint-pen",
        "variants": [
            {
                "id": 40123456789,
                "price": "1033.50",
                "compare_at_price": "1590.00",
                "available": True,
            }
        ]
    }
}

SAMPLE_HTML_PAGE = """
<html>
<body>
  <div class="product-card product-card-style-standard">
    <div class="product-card__wrapper">
      <div class="product-card__info">
        <h3 class="product-card__title">
          <a href="/products/tombow-airpress-pressurized-ballpoint-pen?_pos=1">
            <span>Tombow Airpress Pressurized Ballpoint Pen</span>
          </a>
        </h3>
        <div class="f-price f-price--on-sale">
          <div class="f-price__sale">
            <span class="f-price-item f-price-item--sale">From MRP Rs. 1,033.50</span>
            <span class="f-price-item f-price-item--regular"><s>MRP Rs. 1,590.00</s></span>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div class="product-card">
    <div class="product-card__info">
      <h3 class="product-card__title">
        <a href="/products/tombow-airpress-refill-0-7mm">
          <span>Tombow Airpress Refill 0.7mm</span>
        </a>
      </h3>
      <div class="f-price">
        <span class="f-price-item f-price-item--sale">Rs. 150.00</span>
      </div>
    </div>
  </div>
</body>
</html>
"""

@pytest.mark.asyncio
async def test_scooboo_tier1_suggest_api_success():
    agent = ScoobooScraperAgent()

    mock_suggest_resp = MagicMock()
    mock_suggest_resp.status_code = 200
    mock_suggest_resp.text = "{}"
    mock_suggest_resp.json.return_value = SAMPLE_SUGGEST_JSON

    mock_detail_resp = MagicMock()
    mock_detail_resp.status_code = 200
    mock_detail_resp.text = "{}"
    mock_detail_resp.json.return_value = SAMPLE_DETAIL_JSON

    async def mock_get(url, **kwargs):
        if "suggest.json" in url:
            return mock_suggest_resp
        elif ".json" in url:
            return mock_detail_resp
        return MagicMock(status_code=404, text="")

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=mock_get)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api(
            product_name="Tombow Airpress Pressurized Ballpoint Pen",
            brand="Tombow",
            barcode="",
            catalog_price=1000.0,
        )

    assert candidate is not None
    assert candidate["platform"] == "Scooboo"
    assert candidate["price"] == 1033.50
    assert candidate["mrp"] == 1590.00
    assert candidate["in_stock"] is True
    assert candidate["stock_status"] == "in_stock"
    assert "tombow-airpress-pressurized-ballpoint-pen" in candidate["product_url"]
    assert candidate["scrape_mode"] == "internal_api"
    assert candidate["match_score"] >= 0.70

@pytest.mark.asyncio
async def test_scooboo_query_relaxation():
    agent = ScoobooScraperAgent()

    call_urls = []

    async def mock_get(url, **kwargs):
        call_urls.append(url)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "{}"
        # First query fails with empty list
        if "Tombow+Airpress+Pressurized+Ballpoint+Pen" in url or "Tombow%2BAirpress%2BPressurized" in url or "Ballpoint" in url:
            if len(call_urls) == 1:
                mock_resp.json.return_value = {"resources": {"results": {"products": []}}}
                return mock_resp
        # Relaxed 3-token query succeeds
        if "suggest.json" in url:
            mock_resp.json.return_value = SAMPLE_SUGGEST_JSON
            return mock_resp
        elif ".json" in url:
            mock_resp.json.return_value = SAMPLE_DETAIL_JSON
            return mock_resp
        return MagicMock(status_code=404, text="")

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=mock_get)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api(
            product_name="Tombow Airpress Pressurized Ballpoint Pen Extra Grip",
            brand="Tombow",
            barcode="",
            catalog_price=1000.0,
        )

    assert candidate is not None
    assert len(call_urls) >= 2
    assert candidate["price"] == 1033.50

@pytest.mark.asyncio
async def test_scooboo_refill_filtering():
    agent = ScoobooScraperAgent()

    # Query for pen should NOT pick the refill variant
    mock_suggest_resp = MagicMock()
    mock_suggest_resp.status_code = 200
    mock_suggest_resp.text = "{}"
    mock_suggest_resp.json.return_value = SAMPLE_SUGGEST_JSON

    mock_detail_resp = MagicMock()
    mock_detail_resp.status_code = 200
    mock_detail_resp.text = "{}"
    mock_detail_resp.json.return_value = SAMPLE_DETAIL_JSON

    async def mock_get(url, **kwargs):
        if "suggest.json" in url:
            return mock_suggest_resp
        return mock_detail_resp

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=mock_get)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api(
            product_name="Tombow Airpress Ballpoint Pen",
            brand="Tombow",
            barcode="",
        )

    assert candidate is not None
    assert "refill" not in candidate["product_title"].lower()
    assert candidate["price"] == 1033.50

def test_scooboo_extract_cards_dom():
    agent = ScoobooScraperAgent()
    candidate = agent._extract_cards(
        html_text=SAMPLE_HTML_PAGE,
        target_name="Tombow Airpress Pressurized Ballpoint Pen",
        brand="Tombow",
        barcode="",
        search_url="https://scooboo.in/search?q=Tombow+Airpress",
        catalog_price=1000.0,
    )

    assert candidate is not None
    assert candidate["platform"] == "Scooboo"
    assert candidate["price"] == 1033.50
    assert candidate["mrp"] == 1590.00
    assert candidate["product_url"] == "https://scooboo.in/products/tombow-airpress-pressurized-ballpoint-pen"
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"
    assert candidate["match_score"] >= 0.70

def test_scooboo_extract_cards_refill_exclusion():
    agent = ScoobooScraperAgent()
    # HTML with only refill card
    refill_html = """
    <div class="product-card">
      <div class="product-card__info">
        <h3 class="product-card__title">
          <a href="/products/tombow-airpress-refill-0-7mm">
            <span>Tombow Airpress Refill 0.7mm</span>
          </a>
        </h3>
        <span class="f-price-item--sale">Rs. 150.00</span>
      </div>
    </div>
    """
    candidate = agent._extract_cards(
        html_text=refill_html,
        target_name="Tombow Airpress Ballpoint Pen",
        brand="Tombow",
        barcode="",
        search_url="https://scooboo.in/search?q=Tombow+Airpress",
    )
    # Refill must be ignored when target_name does not ask for refill
    assert candidate is None
