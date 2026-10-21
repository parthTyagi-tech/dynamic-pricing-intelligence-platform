import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agentic.scrapers.platform_scrapers import CaratLaneScraperAgent
from app.services.agentic.scrapers.base_scraper import BotDetectionEncountered, PlatformRateLimitError


@pytest.fixture
def caratlane_agent():
    return CaratLaneScraperAgent()


@pytest.mark.asyncio
async def test_caratlane_tier1_preloaded_state_extraction(caratlane_agent):
    """Verify tier1 extracts product from window.__PRELOADED_STATE__ using raw_decode."""
    state_payload = {
        "listingPage": {
            "listingData": {
                "products": [
                    {
                        "name": "Radiant Fusion Gemstone Stud Earrings",
                        "sku": "JE10160-YGS3SE",
                        "price": 98743,
                        "special_price": 78995,
                        "url": "/jewellery/radiant-fusion-gemstone-stud-earrings-je10160-ygs3se.html",
                        "brand": ["Caratlane"],
                    },
                    {
                        "name": "Unrelated Silver Ring",
                        "sku": "SR001",
                        "price": 5000,
                        "special_price": 4000,
                        "url": "/jewellery/unrelated-silver-ring.html",
                    },
                ]
            }
        }
    }
    # Embed multi-statement trailing JavaScript to test raw_decode boundary safety
    html = (
        "<!DOCTYPE html><html><head><script>"
        f"window.__PRELOADED_STATE__ = {json.dumps(state_payload)};"
        "window.logger = {info: function(){}};"
        "window.isBot = false;"
        "</script></head><body></body></html>"
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await caratlane_agent._tier1_internal_api(
            product_name="Radiant Fusion Gemstone Stud Earrings",
            brand="CaratLane",
            barcode="",
            catalog_price=79000.0,
        )

    assert candidate is not None
    assert candidate["platform"] == "CaratLane"
    assert candidate["price"] == 78995.0
    assert candidate["mrp"] == 98743.0
    assert candidate["product_title"] == "Radiant Fusion Gemstone Stud Earrings"
    assert candidate["product_url"] == "https://www.caratlane.com/jewellery/radiant-fusion-gemstone-stud-earrings-je10160-ygs3se.html"
    assert candidate["url_verified"] is True
    assert candidate["scrape_mode"] == "internal_api"


@pytest.mark.asyncio
async def test_caratlane_tier1_microdata_extraction(caratlane_agent):
    """Verify tier1 extracts schema.org/Product microdata when preloaded state is missing."""
    microdata_html = """
    <!DOCTYPE html>
    <html>
    <body>
        <div itemscope="" itemtype="https://schema.org/Product">
            <link href="https://www.caratlane.com/jewellery/zoey-diamond-round-kids-hoops-je09655-ygs3se.html" itemprop="url"/>
            <meta content="Zoey Diamond Round Kids Hoops" itemprop="name"/>
            <meta content="INR" itemprop="priceCurrency"/>
            <meta content="38493" itemprop="price"/>
            <meta content="45000" itemprop="highPrice"/>
            <meta content="JE09655-YGS3SE" itemprop="sku"/>
        </div>
    </body>
    </html>
    """

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = microdata_html

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        candidate = await caratlane_agent._tier1_internal_api(
            product_name="Zoey Diamond Round Kids Hoops",
            brand="CaratLane",
            barcode="",
            catalog_price=38500.0,
        )

    assert candidate is not None
    assert candidate["platform"] == "CaratLane"
    assert candidate["price"] == 38493.0
    assert candidate["mrp"] == 45000.0
    assert candidate["product_title"] == "Zoey Diamond Round Kids Hoops"
    assert "zoey-diamond-round-kids-hoops" in candidate["product_url"]
    assert candidate["url_verified"] is True


def test_caratlane_dom_fallback_selectors(caratlane_agent):
    """Verify _extract_cards works on standard DOM fallback markup."""
    dom_html = """
    <div class="product-listing">
        <div class="productCard">
            <h2 class="title"><a href="/jewellery/classic-solitaire-diamond-ring.html">Classic Solitaire Diamond Ring</a></h2>
            <div class="price-box">
                <span class="offerPrice">₹52,499</span>
                <span class="strikePrice">₹65,000</span>
            </div>
        </div>
    </div>
    """
    candidate = caratlane_agent._extract_cards(
        html_text=dom_html,
        target_name="Classic Solitaire Diamond Ring",
        brand="CaratLane",
        barcode="",
        search_url="https://www.caratlane.com/catalogsearch/result?q=classic+solitaire",
        catalog_price=52000.0,
    )

    assert candidate is not None
    assert candidate["price"] == 52499.0
    assert candidate["mrp"] == 65000.0
    assert candidate["product_title"] == "Classic Solitaire Diamond Ring"
    assert candidate["product_url"] == "https://www.caratlane.com/jewellery/classic-solitaire-diamond-ring.html"
    assert candidate["url_verified"] is True


@pytest.mark.asyncio
async def test_caratlane_formatted_price_fallback(caratlane_agent):
    """Verify preloaded products with formatted string prices are parsed cleanly."""
    products = [
        {
            "name": "Peepal Leaf Gold Stud Earrings",
            "formatted_price": "₹60,000",
            "formatted_special_price": "₹48,500",
            "url": "/jewellery/peepal-leaf-earrings.html",
        }
    ]
    cand = caratlane_agent._parse_preloaded_products(
        products=products,
        target_name="Peepal Leaf Gold Stud Earrings",
        brand="CaratLane",
        barcode="",
        search_url="https://www.caratlane.com/catalogsearch/result?q=peepal+leaf",
        catalog_price=48000.0,
    )

    assert cand is not None
    assert cand["price"] == 48500.0
    assert cand["mrp"] == 60000.0
    assert cand["product_title"] == "Peepal Leaf Gold Stud Earrings"


@pytest.mark.asyncio
async def test_caratlane_bot_detection_trigger(caratlane_agent):
    """Verify BotDetectionEncountered is raised on Cloudflare / Akamai challenge pages."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "<html><head><title>Access Denied - Akamai Ghost</title></head><body>Reference #18.234</body></html>"

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_resp
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        with pytest.raises(BotDetectionEncountered):
            await caratlane_agent._tier1_internal_api(
                product_name="Diamond Ring",
                brand="CaratLane",
                barcode="",
            )
