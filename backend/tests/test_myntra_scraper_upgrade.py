import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.agentic.scrapers.platform_scrapers import MyntraScraperAgent
from app.services.agentic.scrapers.base_scraper import PlatformRateLimitError, BotDetectionEncountered

SAMPLE_MYX_HTML = """
<!DOCTYPE html>
<html>
<head>
  <script>
    window.__myx = {"searchData":{"results":{"products":[{"productId":12345,"brand":"Roadster","productName":"Men Solid Pure Cotton T-shirt","price":399,"mrp":899,"landingPageUrl":"tshirts/roadster/men-solid-pure-cotton-t-shirt/12345/buy"}]}}};
  </script>
</head>
<body>
  <div>Search results</div>
</body>
</html>
"""

SAMPLE_GATEWAY_JSON = {
    "products": [
        {
            "productId": 67890,
            "brand": "Roadster",
            "productName": "Men Solid Pure Cotton T-shirt",
            "price": 449,
            "mrp": 999,
            "landingPageUrl": "tshirts/roadster/men-solid-pure-cotton-t-shirt/67890/buy",
        }
    ]
}

SAMPLE_DOM_HTML = """
<html>
<body>
  <ul class="results-base">
    <li class="product-base">
      <a href="/tshirts/roadster/men-solid-pure-cotton-t-shirt/12345/buy?pincode=560001">
        <div class="product-productMetaInfo">
          <h3 class="product-brand">Roadster</h3>
          <h4 class="product-product">Men Solid Pure Cotton T-shirt</h4>
          <div class="product-price">
            <span>
              <span class="product-discountedPrice">Rs. 399</span>
              <span class="product-strike">Rs. 899</span>
            </span>
          </div>
        </div>
      </a>
    </li>
  </ul>
</body>
</html>
"""

@pytest.mark.asyncio
async def test_myntra_tier1_window_myx_success():
    agent = MyntraScraperAgent()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = SAMPLE_MYX_HTML

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_resp)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api(
            product_name="Roadster Men Solid Pure Cotton T-shirt",
            brand="Roadster",
            barcode="",
            catalog_price=499.0,
        )

    assert candidate is not None
    assert candidate["platform"] == "Myntra"
    assert candidate["price"] == 399.0
    assert candidate["mrp"] == 899.0
    assert candidate["product_title"] == "Roadster Men Solid Pure Cotton T-shirt"
    assert candidate["product_url"] == "https://www.myntra.com/tshirts/roadster/men-solid-pure-cotton-t-shirt/12345/buy"
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"
    assert candidate["scrape_mode"] == "internal_api"
    assert candidate["match_score"] >= 0.70

@pytest.mark.asyncio
async def test_myntra_tier1_gateway_v2_fallback():
    agent = MyntraScraperAgent()

    empty_page_resp = MagicMock()
    empty_page_resp.status_code = 200
    empty_page_resp.text = "<html><body>No products here</body></html>"

    gateway_resp = MagicMock()
    gateway_resp.status_code = 200
    gateway_resp.text = json.dumps(SAMPLE_GATEWAY_JSON)
    gateway_resp.json.return_value = SAMPLE_GATEWAY_JSON

    async def mock_get(url, **kwargs):
        if "gateway/v2/search" in url:
            return gateway_resp
        return empty_page_resp

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=mock_get)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api(
            product_name="Roadster Men Solid Pure Cotton T-shirt",
            brand="Roadster",
            barcode="",
            catalog_price=499.0,
        )

    assert candidate is not None
    assert candidate["platform"] == "Myntra"
    assert candidate["price"] == 449.0
    assert candidate["mrp"] == 999.0
    assert candidate["product_url"] == "https://www.myntra.com/tshirts/roadster/men-solid-pure-cotton-t-shirt/67890/buy"
    assert candidate["scrape_mode"] == "internal_api"
    assert candidate["match_score"] >= 0.70

@pytest.mark.asyncio
async def test_myntra_brand_deduplication():
    agent = MyntraScraperAgent()
    urls_called = []

    async def mock_get(url, **kwargs):
        urls_called.append(url)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_MYX_HTML
        return mock_resp

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=mock_get)
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await agent._tier1_internal_api(
            product_name="Roadster Roadster Men Solid Pure Cotton T-shirt",
            brand="Roadster",
            barcode="",
            catalog_price=499.0,
        )

    assert candidate is not None
    assert len(urls_called) >= 1
    # Check that slug does not repeat 'roadster-roadster'
    assert "roadster-roadster" not in urls_called[0]
    assert "roadster-men-solid-pure-cotton-t-shirt" in urls_called[0]

def test_myntra_extract_cards_dom():
    agent = MyntraScraperAgent()
    candidate = agent._extract_cards(
        html_text=SAMPLE_DOM_HTML,
        target_name="Roadster Men Solid Pure Cotton T-shirt",
        brand="Roadster",
        barcode="",
        search_url="https://www.myntra.com/roadster-men-solid-pure-cotton-t-shirt",
        catalog_price=499.0,
    )

    assert candidate is not None
    assert candidate["platform"] == "Myntra"
    assert candidate["price"] == 399.0
    assert candidate["mrp"] == 899.0
    assert candidate["product_title"] == "Roadster Men Solid Pure Cotton T-shirt"
    assert candidate["product_url"] == "https://www.myntra.com/tshirts/roadster/men-solid-pure-cotton-t-shirt/12345/buy"
    assert candidate["url_verified"] is True
    assert candidate["stock_status"] == "in_stock"
    assert candidate["match_score"] >= 0.70

@pytest.mark.asyncio
async def test_myntra_bot_detection_and_rate_limit():
    agent = MyntraScraperAgent()

    # Rate limit test (HTTP 429)
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.text = "Too Many Requests"

    mock_session_429 = AsyncMock()
    mock_session_429.get = AsyncMock(return_value=resp_429)
    mock_session_429.__aenter__.return_value = mock_session_429
    mock_session_429.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session_429):
        with pytest.raises(PlatformRateLimitError):
            await agent._tier1_internal_api(
                product_name="Roadster Men Solid Pure Cotton T-shirt",
                brand="Roadster",
                barcode="",
            )

    # Cloudflare challenge test (HTTP 403)
    resp_403 = MagicMock()
    resp_403.status_code = 403
    resp_403.text = "<html><body>Cloudflare challenge cf-turnstile</body></html>"

    mock_session_403 = AsyncMock()
    mock_session_403.get = AsyncMock(return_value=resp_403)
    mock_session_403.__aenter__.return_value = mock_session_403
    mock_session_403.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session_403):
        with pytest.raises(BotDetectionEncountered):
            await agent._tier1_internal_api(
                product_name="Roadster Men Solid Pure Cotton T-shirt",
                brand="Roadster",
                barcode="",
            )
