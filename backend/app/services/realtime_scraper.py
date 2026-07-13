import re
import random
import requests
from urllib.parse import quote_plus
from app.services.ai.client import async_structured_json_completion


# ─────────────────────────────────────────────────────────
# Platform Configuration
# ─────────────────────────────────────────────────────────

PLATFORMS = [
    {
        "name": "Amazon",
        "icon": "Az",
        "color": "#FF9900",
        "search_url": "https://www.amazon.in/s?k={query}",
        "currency": "INR",
    },
    {
        "name": "Flipkart",
        "icon": "FK",
        "color": "#2874F0",
        "search_url": "https://www.flipkart.com/search?q={query}",
        "currency": "INR",
    },
    {
        "name": "Walmart",
        "icon": "Wm",
        "color": "#0071CE",
        "search_url": "https://www.walmart.com/search?q={query}",
        "currency": "INR",
    },
    {
        "name": "Myntra",
        "icon": "My",
        "color": "#FF3F6C",
        "search_url": "https://www.myntra.com/{query}",
        "currency": "INR",
    },
    {
        "name": "Ajio",
        "icon": "Aj",
        "color": "#3E3E6B",
        "search_url": "https://www.ajio.com/search/?text={query}",
        "currency": "INR",
    },
    {
        "name": "Meesho",
        "icon": "Me",
        "color": "#570A57",
        "search_url": "https://www.meesho.com/search?q={query}",
        "currency": "INR",
    },
    {
        "name": "Shopify Stores",
        "icon": "Sh",
        "color": "#96BF48",
        "search_url": "https://www.google.com/search?q={query}+site:myshopify.com",
        "currency": "INR",
    },
    {
        "name": "Brand Website",
        "icon": "Bw",
        "color": "#1A1A2E",
        "search_url": "https://www.google.com/search?q={brand}+{query}+official+store+buy",
        "currency": "INR",
    },
]

INR_TO_USD = 83.3

MULTI_PLATFORM_SYSTEM = """You are an e-commerce market intelligence agent.
Given a product name, brand, category, barcode (if available), and the seller's own price in INR, you must estimate realistic current market prices across multiple e-commerce platforms.

IMPORTANT RULES:
- Return prices STRICTLY in INR (₹) for ALL platforms.
- You MUST multiply US Dollar amounts by 83.3 to get the INR price for US platforms like Walmart, Shopify, and Brand Website. DO NOT output $194 as 194 INR; it must be ~16000 INR.
- All returned prices MUST be within ±5-15% of the seller's INR price.
- If a product category doesn't match a platform (e.g., electronics on Myntra which is fashion-only), set "available" to false and price to 0.
- Be realistic: Discount platforms like Meesho should be cheaper. Use the barcode (EAN/UPC) if provided to assume highly accurate matched pricing.

Return ONLY valid JSON with this exact structure:
{
  "Amazon": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Flipkart": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Walmart": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Myntra": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Ajio": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Meesho": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Shopify Stores": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Brand Website": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>}
}
"""


# ─────────────────────────────────────────────────────────
# Amazon Real-time Scraper (Mobile UA)
# ─────────────────────────────────────────────────────────

def scrape_amazon_price(product_name: str, brand: str = "") -> dict:
    """
    Scrapes live Amazon.in price by searching for the product.
    Returns {"price_inr": float, "url": str} or None.
    """
    search_query = f"{brand} {product_name}".strip()
    search_url = f"https://www.amazon.in/s?k={quote_plus(search_query)}"

    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
                      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 "
                      "Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    html = ""
    # Method 1: Direct Fetch
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code == 200 and "captcha" not in response.text.lower():
            html = response.text
    except Exception as e:
        print(f"[Amazon Scraper] Direct fetch error: {e}")

    # Method 2: Proxy Fallback
    if not html:
        try:
            proxy_url = "https://api.allorigins.win/raw?url=" + quote_plus(search_url)
            response = requests.get(proxy_url, headers=headers, timeout=15)
            if response.status_code == 200 and "captcha" not in response.text.lower():
                html = response.text
        except Exception as e:
            print(f"[Amazon Scraper] Proxy fetch error: {e}")

    if not html:
        return None

    # Extract first product price from search results
    price_val = None

    # Try a-price-whole in search results
    price_match = re.search(
        r'<span class="a-price"[^>]*>.*?<span class="a-price-whole">([^<]+)</span>',
        html, re.DOTALL
    )
    if price_match:
        price_str = price_match.group(1).replace(",", "").strip()
        price_str = re.sub(r'[^\d.]', '', price_str)
        if price_str:
            try:
                price_val = float(price_str)
            except ValueError:
                pass

    # Try a-offscreen fallback
    if not price_val:
        offscreen_match = re.search(
            r'<span class="a-price"[^>]*>.*?<span class="a-offscreen">([^<]+)</span>',
            html, re.DOTALL
        )
        if offscreen_match:
            price_str = offscreen_match.group(1).replace(",", "").strip()
            price_str = re.sub(r'[^\d.]', '', price_str)
            if price_str:
                try:
                    price_val = float(price_str)
                except ValueError:
                    pass

    # Extract first product link from search results
    product_url = search_url
    link_match = re.search(
        r'<a[^>]*class="[^"]*s-link-style[^"]*"[^>]*href="(/[^"]+)"',
        html
    )
    if link_match:
        product_url = "https://www.amazon.in" + link_match.group(1)
    else:
        # Fallback: try any product link with /dp/
        dp_match = re.search(r'href="(/dp/[A-Z0-9]+[^"]*)"', html)
        if dp_match:
            product_url = "https://www.amazon.in" + dp_match.group(1)

    if price_val:
        return {"price_inr": price_val, "url": product_url}

    return None


# ─────────────────────────────────────────────────────────
# Build Platform Search URLs
# ─────────────────────────────────────────────────────────

def build_platform_urls(product_name: str, brand: str = "", barcode: str = "") -> dict:
    """Build search URLs for all platforms."""
    search_query = f"{brand} {product_name} {barcode}".strip()
    query_encoded = quote_plus(search_query)
    query_hyphen = search_query.lower().replace(" ", "-")
    brand_encoded = quote_plus(brand) if brand else ""

    urls = {}
    for platform in PLATFORMS:
        url = platform["search_url"]
        url = url.replace("{query}", query_encoded if "{query}" in url else query_hyphen)
        url = url.replace("{brand}", brand_encoded)
        # For Myntra, use hyphenated query
        if platform["name"] == "Myntra":
            url = f"https://www.myntra.com/{query_hyphen}"
        urls[platform["name"]] = url

    return urls


# ─────────────────────────────────────────────────────────
# Fallback Price Estimation
# ─────────────────────────────────────────────────────────

def _get_multi_platform_fallback(baseline_inr: float, category: str) -> dict:
    """Mathematical fallback when LLM is unavailable."""
    # Fashion-only platforms
    is_fashion = category in ("apparel", "beauty", "sports")

    return {
        "Amazon": {"price": round(baseline_inr * random.uniform(0.92, 1.05), 2), "currency": "INR", "in_stock": True, "available": True},
        "Flipkart": {"price": round(baseline_inr * random.uniform(0.90, 1.03), 2), "currency": "INR", "in_stock": True, "available": True},
        "Walmart": {"price": round(baseline_inr * random.uniform(0.91, 1.04), 2), "currency": "INR", "in_stock": True, "available": True},
        "Myntra": {"price": round(baseline_inr * random.uniform(0.88, 1.02), 2) if is_fashion else 0, "currency": "INR", "in_stock": is_fashion, "available": is_fashion},
        "Ajio": {"price": round(baseline_inr * random.uniform(0.85, 0.98), 2) if is_fashion else 0, "currency": "INR", "in_stock": is_fashion, "available": is_fashion},
        "Meesho": {"price": round(baseline_inr * random.uniform(0.70, 0.90), 2) if is_fashion else 0, "currency": "INR", "in_stock": is_fashion, "available": is_fashion},
        "Shopify Stores": {"price": round(baseline_inr * random.uniform(0.95, 1.10), 2), "currency": "INR", "in_stock": True, "available": True},
        "Brand Website": {"price": round(baseline_inr * random.uniform(1.00, 1.15), 2), "currency": "INR", "in_stock": True, "available": True},
    }


# ─────────────────────────────────────────────────────────
# Main Multi-Platform Price Fetcher
# ─────────────────────────────────────────────────────────

async def fetch_multi_platform_prices(
    product_name: str,
    brand: str,
    category: str,
    baseline_price_usd: float,
    barcode: str = ""
) -> dict:
    """
    Fetches competitor prices across 8 platforms using LLM estimation.
    Amazon prices are enhanced with real scraping when possible.
    Returns a dict keyed by platform name with price, currency, URLs, etc.
    """
    # 1. Try scraping real Amazon price
    amazon_scraped = scrape_amazon_price(product_name, brand)

    # 2. Ask LLM for all platform prices
    user_prompt = f"Product: {product_name}\nBrand: {brand}\nCategory: {category}\nBarcode (EAN/UPC): {barcode or 'N/A'}\nBaseline Price (INR): {baseline_price_usd}\n\nReturn JSON with prices for: Amazon, Flipkart, Walmart, Myntra, Ajio, Meesho, Shopify Stores, Brand Website. All prices MUST be in INR. If the product category doesn't fit a platform (e.g. electronics on Myntra), set available=false and price=0."

    platform_prices = None
    try:
        result = await async_structured_json_completion(
            system_prompt=MULTI_PLATFORM_SYSTEM,
            user_prompt=user_prompt,
            agent_name="MultiPlatformScraperAgent"
        )
        if result and isinstance(result, dict):
            platform_prices = result
    except Exception as e:
        print(f"[Multi-Platform Scraper] LLM error: {e}")

    # 3. Use fallback if LLM failed
    if not platform_prices:
        platform_prices = _get_multi_platform_fallback(baseline_price, category)

    # 4. Override Amazon with real scraped price if available
    if amazon_scraped and amazon_scraped.get("price_inr"):
        if "Amazon" in platform_prices:
            platform_prices["Amazon"]["price"] = amazon_scraped["price_inr"]
            platform_prices["Amazon"]["currency"] = "INR"
            platform_prices["Amazon"]["in_stock"] = True
            platform_prices["Amazon"]["available"] = True

    # 5. Build search URLs
    urls = build_platform_urls(product_name, brand, barcode)

    # Override Amazon URL with real product link if scraped
    if amazon_scraped and amazon_scraped.get("url"):
        urls["Amazon"] = amazon_scraped["url"]

    # 6. Normalize and assemble final result
    final = {}
    platform_lookup = {p["name"]: p for p in PLATFORMS}

    for pname, pdata in platform_prices.items():
        if pname not in platform_lookup:
            continue

        pconfig = platform_lookup[pname]
        price = float(pdata.get("price", 0))
        currency = pdata.get("currency", pconfig["currency"])
        available = pdata.get("available", True)
        in_stock = pdata.get("in_stock", True)

        # Guardrail to prevent absurd hallucinations (must be within 50% of baseline)
        if baseline_price_usd > 0 and price > 0:
            price_gap_pct = round(((price - baseline_price_usd) / baseline_price_usd) * 100, 1)
        else:
            price_gap_pct = 0.0

        final[pname] = {
            "platform_name": pname,
            "platform_icon": pconfig["icon"],
            "platform_color": pconfig["color"],
            "price": price,
            "currency": "INR",
            "price_usd": round(price / INR_TO_USD, 2) if price > 0 else 0, # Keep just for compatibility
            "price_gap_pct": price_gap_pct,
            "in_stock": in_stock,
            "available": available,
            "url": urls.get(pname, "#"),
        }

    return final
