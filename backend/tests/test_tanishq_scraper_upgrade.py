import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agentic.scrapers.platform_scrapers import TanishqScraperAgent
from app.services.agentic.scrapers.base_scraper import BotDetectionEncountered, PlatformRateLimitError


@pytest.fixture
def tanishq_agent():
    return TanishqScraperAgent()


@pytest.mark.asyncio
async def test_tanishq_tier1_internal_api_gtmdata_extraction(tanishq_agent):
    """Verify tier1 extracts product from SFCC div.product-tile with data-gtmdata JSON."""
    gtm_payload = {
        "item_id": "515923CUTAA00",
        "item_name": "Twinkle Trinket 22 Kt Gold Chain",
        "affiliation": "Tanishq Online store",
        "price": 96136,
        "currency": "INR",
        "item_brand": "MIA",
        "stockStatus": "in stock",
    }
    tile_html = f"""
    <!DOCTYPE html>
    <html>
    <body>
        <div class="product-tile" data-gtmdata='{json.dumps(gtm_payload)}'>
            <a class="product-tile__name" href="https://www.tanishq.co.in/product/twinkle-trinket-22-kt-gold-chain-515923cutaa00.html">
                Twinkle Trinket 22 Kt Gold Chain
            </a>
            <span class="sales"><span class="value" content="96136">₹ 96,136</span></span>
            <span class="strike-through">Price reduced from ₹ 97,444 to</span>
        </div>
    </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = tile_html

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await tanishq_agent._tier1_internal_api(
            product_name="Twinkle Trinket 22 Kt Gold Chain",
            brand="Tanishq",
            barcode="",
            catalog_price=96000.0,
        )

    assert candidate is not None
    assert candidate["platform"] == "Tanishq"
    assert candidate["price"] == 96136.0
    assert candidate["mrp"] == 97444.0
    assert candidate["product_title"] == "Twinkle Trinket 22 Kt Gold Chain"
    assert "twinkle-trinket-22-kt-gold-chain" in candidate["product_url"]
    assert candidate["url_verified"] is True
    assert candidate["scrape_mode"] == "internal_api"


@pytest.mark.asyncio
async def test_tanishq_tier1_structured_data_fallback(tanishq_agent):
    """Verify tier1 extracts product from application/ld+json when tiles are absent."""
    ld_json = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Luminous Link 22KT Gold Chain",
        "offers": {
            "@type": "Offer",
            "price": "111684",
            "priceCurrency": "INR",
            "availability": "https://schema.org/InStock",
            "url": "https://www.tanishq.co.in/product/luminous-link-22kt-gold-chain.html",
        },
    }
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">{json.dumps(ld_json)}</script>
    </head>
    <body></body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await tanishq_agent._tier1_internal_api(
            product_name="Luminous Link 22KT Gold Chain",
            brand="Tanishq",
            barcode="",
            catalog_price=111000.0,
        )

    assert candidate is not None
    assert candidate["platform"] == "Tanishq"
    assert candidate["price"] == 111684.0
    assert candidate["product_title"] == "Luminous Link 22KT Gold Chain"
    assert candidate["scrape_mode"] == "internal_api"


def test_tanishq_dom_fallback_selectors(tanishq_agent):
    """Verify _extract_cards parses pure SFCC DOM elements without data-gtmdata."""
    dom_html = """
    <div class="product-listing">
        <div class="product-tile">
            <a class="product-tile__name" href="/product/sleek-twist-gold-chain-502822cjuaa00.html">
                Sleek Twist Gold Chain
            </a>
            <div class="price">
                <span class="sales"><span class="value" content="72918">₹ 72,918</span></span>
                <span class="strike-through">₹ 73,910</span>
            </div>
        </div>
    </div>
    """
    candidate = tanishq_agent._extract_cards(
        html_text=dom_html,
        target_name="Sleek Twist Gold Chain",
        brand="Tanishq",
        barcode="",
        search_url="https://www.tanishq.co.in/shop?q=sleek+twist",
        catalog_price=73000.0,
    )

    assert candidate is not None
    assert candidate["price"] == 72918.0
    assert candidate["mrp"] == 73910.0
    assert candidate["product_title"] == "Sleek Twist Gold Chain"
    assert candidate["product_url"] == "https://www.tanishq.co.in/product/sleek-twist-gold-chain-502822cjuaa00.html"
    assert candidate["url_verified"] is True


@pytest.mark.asyncio
async def test_tanishq_relaxed_query_retry(tanishq_agent):
    """Verify long queries retry with first 3 tokens when initial search has no matches."""
    empty_resp = MagicMock()
    empty_resp.status_code = 200
    empty_resp.text = "<html><body><div class='no-results'>No products found</div></body></html>"

    success_gtm = {
        "item_name": "Glided Elegance Gold Chain",
        "price": 65526,
        "stockStatus": "in stock",
    }
    relaxed_resp = MagicMock()
    relaxed_resp.status_code = 200
    relaxed_resp.text = f"""
    <html><body>
        <div class="product-tile" data-gtmdata='{json.dumps(success_gtm)}'>
            <a class="product-tile__name" href="/product/glided-elegance-gold-chain.html">Glided Elegance Gold Chain</a>
        </div>
    </body></html>
    """

    mock_session = AsyncMock()
    mock_session.get.side_effect = [empty_resp, relaxed_resp]
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await tanishq_agent._tier1_internal_api(
            product_name="Glided Elegance Gold Chain 22KT",
            brand="Tanishq",
            barcode="",
            catalog_price=65000.0,
        )

    assert candidate is not None
    assert candidate["price"] == 65526.0
    assert candidate["product_title"] == "Glided Elegance Gold Chain"
    assert candidate["product_url"] == "https://www.tanishq.co.in/product/glided-elegance-gold-chain.html"


@pytest.mark.asyncio
async def test_tanishq_bot_detection_trigger(tanishq_agent):
    """Verify BotDetectionEncountered is raised on Cloudflare / PerimeterX challenges."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "<html><head><title>Access Denied</title></head><body>Request blocked by PerimeterX</body></html>"

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        with pytest.raises(BotDetectionEncountered):
            await tanishq_agent._tier1_internal_api(
                product_name="Gold Ring",
                brand="Tanishq",
                barcode="",
            )
