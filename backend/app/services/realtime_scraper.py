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
        "name": "Ebay",
        "icon": "Eb",
        "color": "#0064D2",
        "search_url": "https://www.ebay.com/sch/i.html?_nkw={query}",
        "currency": "USD",
    },
    {
        "name": "BestBuy",
        "icon": "BB",
        "color": "#0046BE",
        "search_url": "https://www.bestbuy.com/site/searchpage.jsp?st={query}",
        "currency": "USD",
    },
    {
        "name": "Target",
        "icon": "Tg",
        "color": "#CC0000",
        "search_url": "https://www.target.com/s?searchTerm={query}",
        "currency": "USD",
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

from crawl4ai import AsyncWebCrawler, BrowserConfig


def _compute_match_score(product_title: str, brand: str, match_keywords: list = None) -> float:
    """
    Score how well a scraped product title matches the target product.
    Returns 0.0 to 1.0.  Brand match is mandatory — if the brand doesn't
    appear anywhere in the title the score is 0.
    Also, if any model-specific keyword (like 'wh-1000xm4' or 'venture') is present
    in match_keywords, it must exist in the title, otherwise score is 0.
    """
    title_lower = product_title.lower()
    brand_lower = brand.lower().strip() if brand else ""
    
    # Alphanumeric normalization helper
    def norm(text: str) -> str:
        return re.sub(r'[^a-z0-9]', '', text.lower())

    # ── Brand gate ──────────────────────────────────────
    if brand_lower:
        brand_words = brand_lower.split()
        if brand_lower not in title_lower:
            if not all(bw in title_lower for bw in brand_words):
                return 0.0

    # ── Model Specific Gate ─────────────────────────────
    title_norm = norm(title_lower)
    if match_keywords:
        model_keywords = [kw for kw in match_keywords if kw.lower() != brand_lower and kw.lower() not in brand_lower]
        if model_keywords:
            if not any(norm(mkw) in title_norm for mkw in model_keywords):
                return 0.0

    # ── Keyword overlap ─────────────────────────────────
    keywords = match_keywords if match_keywords else []
    if not keywords:
        return 0.5

    matched = sum(1 for kw in keywords if norm(kw) in title_norm)
    return matched / len(keywords)


# Minimum score required to accept a search result as a genuine match.
_MIN_MATCH_SCORE = 0.25


async def scrape_platform_with_crawl4ai(
    platform_name: str,
    search_url: str,
    brand: str = "",
    match_keywords: list = None,
    baseline_price: float = 0,
    description: str = "",
) -> dict:
    """
    Scrapes a platform search page with Crawl4AI, extracts every product card,
    scores each one against *brand + match_keywords*, and returns only the
    best-matching product's price and direct URL.

    Returns ``None`` when no product with a sufficient match score is found
    (the caller should treat this as "product not available on this platform").
    """
    import os
    if os.environ.get("MOCK_SCRAPER", "false").lower() == "true":
        return None

    html = ""
    markdown_content = ""
    try:
        browser_config = BrowserConfig(
            headless=True,
            enable_stealth=True,
            user_agent_mode="random",
        )
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=search_url)
            html = result.html
            markdown_content = result.markdown
    except Exception as e:
        print(f"[Crawl4AI {platform_name}] Crawl error: {e}")
        return None

    if not html:
        return None

    candidates = []  # list of (score, price, url, title)

    # ═══════════════════════════════════════════════════════
    #  REGEX PARSING (FLIPKART ONLY)
    # ═══════════════════════════════════════════════════════
    if platform_name == "Flipkart":
        seen = set()
        for m in re.finditer(r'href="(/[^"]*?/p/[^"]*)"', html):
            rel_url = m.group(1)
            # deduplicate
            prod_id = rel_url.split("/p/")[1].split("?")[0] if "/p/" in rel_url else rel_url
            if prod_id in seen:
                continue
            seen.add(prod_id)

            # derive title from URL slug  (e.g.  /venzina-full-sleeve-solid-men-jacket/p/...)
            slug = rel_url.split("/p/")[0].lstrip("/").split("/")[-1] if "/p/" in rel_url else ""
            slug_title = slug.replace("-", " ").title()

            # also try real title from surrounding HTML
            ctx_start = m.start() - 500
            if ctx_start < 0:
                ctx_start = 0
            ctx = html[ctx_start:m.end() + 3000]
            real_title_match = re.search(
                r'class="[^"]*(?:wjcEIp|KzDlHZ|WKTcLC|IRpwTa|s1Q9rs|pIpigb)[^"]*"[^>]*>([^<]+)<', ctx
            )
            title = real_title_match.group(1).strip() if real_title_match else slug_title
            if not title:
                continue

            # price — forward context only
            fwd_ctx = html[m.end():m.end() + 3000]
            price_match = re.search(r'class="[^"]*(?:Nx9bqj|hZ3P6w)[^"]*"[^>]*>[^0-9]*([\d,]+)', fwd_ctx)
            if not price_match:
                price_match = re.search(r'[\u20b9][\s]*([\d,]+)', fwd_ctx)
            if not price_match:
                continue
            price_str = re.sub(r'[^\d.]', '', price_match.group(1).replace(",", ""))
            if not price_str:
                continue
            try:
                price = float(price_str)
            except ValueError:
                continue

            # We just append it to a raw list for LLM selection later
            url = "https://www.flipkart.com" + rel_url.split("&amp;")[0]
            candidates.append((0.0, price, url, title))

    # ═══════════════════════════════════════════════════════
    #  LLM EXTRACTION (Myntra, Ajio, Meesho, Walmart, Shopify, Brand Website, etc.)
    # ═══════════════════════════════════════════════════════
    else:
        # We use LLM extraction for 100% accuracy on all other platforms.
        from app.services.ai.client import async_structured_json_completion
        import json
        
        # Use up to first 12,000 chars of markdown to avoid massive prompts, 
        # usually search results are near the top.
        content_chunk = markdown_content[:12000] if markdown_content else ""
        if content_chunk:
            schema_str = """
{
  "found": true/false (Whether an exact or very highly similar matching product was found),
  "product_title": "The full title of the matching product found",
  "price_inr": 1234.50 (The exact price of the product in INR as a float),
  "url": "The full URL of the product if found"
}
"""
            system_prompt = f"You are an expert e-commerce data extractor."
            user_prompt = f"""I will give you the markdown text of a search results page from {platform_name}.
Search URL: {search_url}

Your Goal:
Look for the exact product matching the brand "{brand}" and keywords "{' '.join(match_keywords or [])}".
Product Description/Attributes to strictly match:
{description}

CRITICAL MATCHING RULES:
You must strictly match the product based on specific attributes like color, storage, size, functionality, and exact model name provided in the description.
Do NOT match variants. If the target product specifies a base model, do not select a "Pro", "Plus", or "Max" variant (and vice versa). If a specific size, storage, or color is requested, do not select a different one.

If you find a highly relevant exact match, extract its full title, its price in INR (just the number), and its product link/URL.
If the price is in USD (e.g. from DuckDuckGo Walmart results), multiply it by 83 to convert to INR.
If no valid product perfectly matches the criteria, OR if you cannot find a valid product URL/link for the matched item in the markdown, set "found" to false and price_inr to 0.

You must respond ONLY with a JSON object matching this schema:
{schema_str}

Markdown Content:
{content_chunk}
"""
            try:
                # Debug print
                print(f"--- [LLM PROMPT {platform_name}] ---\n{user_prompt[:500]}...\n------------------")
                
                result_json = await async_structured_json_completion(system_prompt=system_prompt, user_prompt=user_prompt, agent_name="ScraperExtractionAgent")
                
                print(f"--- [LLM RESULT {platform_name}] ---\n{result_json}\n------------------")
                
                if result_json and result_json.get("found"):
                    price = float(result_json.get("price_inr", 0))
                    if price > 0:
                        url = str(result_json.get("url", "")).strip()
                        if url and url.startswith("/"):
                            if platform_name == "Myntra": url = "https://www.myntra.com" + url
                            elif platform_name == "Amazon": url = "https://www.amazon.in" + url
                            elif platform_name == "Ajio": url = "https://www.ajio.com" + url
                            elif platform_name == "Meesho": url = "https://www.meesho.com" + url
                            elif platform_name == "Walmart": url = "https://www.walmart.com" + url
                            elif platform_name == "Ebay": url = "https://www.ebay.com" + url
                            elif platform_name == "BestBuy": url = "https://www.bestbuy.com" + url
                            elif platform_name == "Target": url = "https://www.target.com" + url
                        
                        # If LLM didn't extract a valid product URL, reject the match to avoid returning the search page
                        if not url or url == search_url or len(url) < 10:
                            print(f"[Crawl4AI {platform_name}] LLM found product but no valid URL. Rejecting.")
                        else:
                            # Give it a perfect score since LLM verified it
                            candidates.append((1.0, price, url, result_json.get("product_title", "LLM Extracted Match")))
            except Exception as e:
                print(f"[Crawl4AI {platform_name}] LLM Extraction Error: {e}")

    if baseline_price > 0:
        min_sane = baseline_price * 0.15   # reject if < 15% of baseline
        max_sane = baseline_price * 5.0    # reject if > 5x baseline
        candidates = [
            c for c in candidates
            if min_sane <= c[1] <= max_sane
        ]

    # ═══════════════════════════════════════════════════════
    #  LLM SELECTION FOR FLIPKART
    # ═══════════════════════════════════════════════════════
    if platform_name in ["Flipkart"] and candidates:
        from app.services.ai.client import async_structured_json_completion
        import json
        
        # Prepare candidate list for LLM
        candidate_list_json = json.dumps([
            {"title": c[3], "price": c[1], "url": c[2]}
            for c in candidates
        ], indent=2)

        schema_str = """
{
  "exact_match_found": true/false (Whether an exact match was found in the candidate list),
  "matched_product_url": "The full url of the exact match from the list",
  "matched_product_price": 1234.50 (The price of the matched product)
}
"""
        system_prompt = "You are a strict product matching AI for e-commerce."
        user_prompt = f"""I have scraped a list of candidate products from {platform_name}.
Target Product Brand: {brand}
Target Keywords: {' '.join(match_keywords or [])}
Target Product Description/Attributes:
{description}

CRITICAL MATCHING RULES:
You must strictly match the product based on specific attributes like color, storage, size, functionality, and exact model name provided in the description.
Do NOT match variants. If the target product specifies a base model, do not select a "Pro", "Plus", or "Max" variant (and vice versa). If a specific size, storage, or color is requested, do not select a different one.

Here are the candidates:
{candidate_list_json}

Review the candidates carefully. If you find the EXACT product matching all criteria, return exact_match_found: true, along with its url and price. If no candidate is an exact match, return exact_match_found: false.

You must respond ONLY with a JSON object matching this schema:
{schema_str}
"""
        try:
            print(f"--- [LLM PROMPT {platform_name} Selection] ---\n{user_prompt[:500]}...\n------------------")
            result_json = await async_structured_json_completion(system_prompt=system_prompt, user_prompt=user_prompt, agent_name="ScraperSelectionAgent")
            print(f"--- [LLM RESULT {platform_name} Selection] ---\n{result_json}\n------------------")
            
            if result_json and result_json.get("exact_match_found"):
                # Overwrite candidates with just the LLM selected one, given a perfect score of 1.0
                candidates = [(1.0, result_json.get("matched_product_price", 0), result_json.get("matched_product_url", ""), "LLM Selected Exact Match")]
            else:
                candidates = [] # No exact match found
        except Exception as e:
            print(f"[Crawl4AI {platform_name}] LLM Selection Error: {e}")
            candidates = []

    # ── Pick the best candidate ─────────────────────────────
    if not candidates:
        return None

    # Sort by score descending, then by price ascending (prefer cheapest among equal scores)
    candidates.sort(key=lambda c: (-c[0], c[1]))
    best_score, best_price, best_url, best_title = candidates[0]

    if best_score < _MIN_MATCH_SCORE:
        print(f"[Crawl4AI {platform_name}] No matching product found (best: '{best_title}' score={best_score:.2f})")
        return None

    print(f"[Crawl4AI {platform_name}] MATCHED: '{best_title}' score={best_score:.2f} price={best_price}")
    return {"price_inr": best_price, "url": best_url}


# ─────────────────────────────────────────────────────────
# Build Platform Search URLs
# ─────────────────────────────────────────────────────────

def build_platform_urls(search_query: str, brand: str = "") -> dict:
    """Build search URLs for all platforms."""
    # Ensure brand is not duplicated at the start of the query
    brand_lower = brand.lower().strip() if brand else ""
    query_clean = search_query.strip()
    if brand_lower and not query_clean.lower().startswith(brand_lower):
        query_clean = f"{brand} {query_clean}"
        
    query_encoded = quote_plus(query_clean)
    query_hyphen = query_clean.lower().replace(" ", "-")
    brand_encoded = quote_plus(brand) if brand else ""

    urls = {}
    for platform in PLATFORMS:
        url = platform["search_url"]
        url = url.replace("{query}", query_encoded if "{query}" in url else query_hyphen)
        url = url.replace("{brand}", brand_encoded)
        # For Amazon, add brand filter to narrow results to exact brand
        if platform["name"] == "Amazon" and brand:
            url += f"&rh=p_89%3A{quote_plus(brand)}"
            
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


def verify_direct_page_price(url: str, platform_name: str) -> dict:
    """
    Attempts to fetch a direct e-commerce product URL and extract the 100% verified
    real-time price and stock status from meta tags or Schema.org JSON-LD.
    Returns a dict with 'price' (in platform's local currency), 'currency', and 'in_stock' if successful, else None.
    """
    import requests
    import re
    import json
    from bs4 import BeautifulSoup
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    
    # Clean DDG redirect wraps if any
    if "duckduckgo.com/y.js" in url or "duckduckgo.com/l/?" in url:
        return None
        
    try:
        print(f"[Direct Page Verifier] Fetching {platform_name} direct URL: {url[:60]}...")
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code != 200:
            print(f"[Direct Page Verifier] {platform_name} direct fetch status code: {r.status_code}")
            return None
            
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # 1. Try to find standard JSON-LD Schema.org product data
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '')
                # Handle list of schemas or single object
                if isinstance(data, list):
                    product_data = next((item for item in data if item.get("@type") == "Product" or "Offers" in item or item.get("@type") == "Schema"), None)
                    # If product data is nested
                    if not product_data:
                        for item in data:
                            if "@graph" in item:
                                product_data = next((sub for sub in item["@graph"] if sub.get("@type") == "Product"), None)
                                if product_data:
                                    break
                else:
                    product_data = data if data.get("@type") == "Product" else None
                    if not product_data and "@graph" in data:
                        product_data = next((sub for sub in data["@graph"] if sub.get("@type") == "Product"), None)
                
                if product_data:
                    offers = product_data.get("offers")
                    if isinstance(offers, list) and offers:
                        offers = offers[0]
                    
                    if offers:
                        # Extract price (could be string or float)
                        raw_price = offers.get("price")
                        if raw_price:
                            # Strip currency symbols/commas if string
                            if isinstance(raw_price, str):
                                raw_price = re.sub(r'[^\d.]', '', raw_price)
                            price = float(raw_price)
                            currency = offers.get("priceCurrency", "USD")
                            availability = str(offers.get("availability", "")).lower()
                            in_stock = "outofstock" not in availability and "discontinued" not in availability
                            if price > 0:
                                print(f"[Direct Page Verifier] Match JSON-LD: {price} {currency} (InStock: {in_stock})")
                                return {"price": price, "currency": currency, "in_stock": in_stock}
            except Exception as ex:
                continue
                
        # 2. Try to find OpenGraph / Twitter meta tags
        meta_price = soup.find('meta', property=re.compile(r'(product:price:amount|og:price:amount|twitter:price:amount)', re.I))
        # Fallback names attribute
        if not meta_price:
            meta_price = soup.find('meta', attrs={"name": re.compile(r'(product:price:amount|price)', re.I)})
            
        meta_currency = soup.find('meta', property=re.compile(r'(product:price:currency|og:price:currency|twitter:price:currency)', re.I))
        if not meta_currency:
            meta_currency = soup.find('meta', attrs={"name": re.compile(r'(product:price:currency|currency)', re.I)})
            
        meta_availability = soup.find('meta', property=re.compile(r'(product:availability|og:availability)', re.I))
        if not meta_availability:
            meta_availability = soup.find('meta', attrs={"name": re.compile(r'(product:availability|availability)', re.I)})
        
        if meta_price:
            try:
                raw_price = meta_price.get('content', '0')
                raw_price = re.sub(r'[^\d.]', '', raw_price)
                price = float(raw_price)
                currency = (meta_currency.get('content') if meta_currency else 'USD') or 'USD'
                availability = str(meta_availability.get('content', '') if meta_availability else 'instock').lower()
                in_stock = 'instock' in availability or 'in_stock' in availability or not availability
                if price > 0:
                    print(f"[Direct Page Verifier] Match MetaTags: {price} {currency} (InStock: {in_stock})")
                    return {"price": price, "currency": currency, "in_stock": in_stock}
            except Exception:
                pass
                
    except Exception as e:
        print(f"[Direct Page Verifier] Error fetching/parsing {platform_name} page: {e}")
        
    return None


# ─────────────────────────────────────────────────────────
# Main Multi-Platform Price Fetcher
# ─────────────────────────────────────────────────────────
import asyncio
import json

async def stream_multi_platform_prices(
    search_query: str,
    brand: str,
    category: str,
    baseline_price_inr: float = 0,
    barcode: str = "",
    description: str = "",
    product_id: str = None
):
    """
    Scrapes DuckDuckGo HTML results for the product across multiple storefront sites
    in a single request, then extracts structured prices and URLs using the LLM.
    Integrates cached direct URL checks and meta tag/JSON-LD verification to guarantee
    accuracy, freshness, and speed while minimizing search engine rate limit hits.
    """
    import json
    import requests
    import urllib.parse
    from bs4 import BeautifulSoup
    from app.services.ai.client import async_structured_json_completion
    
    product_name = search_query
    
    # 0. Set up targets configuration
    pconfigs = {
        "Amazon": {"icon": "Az", "color": "#FF9900", "domains": ["amazon.in", "amazon.com"]},
        "Flipkart": {"icon": "FK", "color": "#2874F0", "domains": ["flipkart.com"]},
        "Walmart": {"icon": "Wm", "color": "#0071CE", "domains": ["walmart.com"]},
        "Ebay": {"icon": "Eb", "color": "#0064D2", "domains": ["ebay.com"]},
        "BestBuy": {"icon": "BB", "color": "#0046BE", "domains": ["bestbuy.com"]},
        "Target": {"icon": "Tg", "color": "#CC0000", "domains": ["target.com"]}
    }
    
    extracted = {}
    platforms_to_search = []
    
    # Send initial status event to client
    yield f"data: {json.dumps({'status': 'started', 'message': 'Checking cached URLs and live page verification...'})}\n\n"
    
    # 1. First-Pass Cache Lookup & Direct Page Verification
    for pname in pconfigs.keys():
        cached_url = None
        if product_id:
            try:
                from flask import current_app
                from app.models.market_data import CompetitorPrice
                with current_app.app_context():
                    # Query the database for the most recent competitor price entry with a valid URL
                    last_price = CompetitorPrice.query.filter(
                        CompetitorPrice.product_id == product_id,
                        CompetitorPrice.competitor_name == pname,
                        CompetitorPrice.product_url.isnot(None),
                        CompetitorPrice.product_url != ""
                    ).order_by(CompetitorPrice.checked_at.desc()).first()
                    if last_price:
                        cached_url = last_price.product_url
            except Exception as ex:
                print(f"[URL Cache] Error querying database for {pname}: {ex}")
                
        if cached_url:
            print(f"[Hybrid Scraper] Found cached URL for {pname}: {cached_url}")
            # Verify the price of the cached URL directly (freshness check)
            direct_match = verify_direct_page_price(cached_url, pname)
            if direct_match:
                # Convert price to INR if currency is USD
                final_price = direct_match["price"]
                if direct_match["currency"] == "USD":
                    final_price = round(final_price * 83.3, 2)
                    
                extracted[pname] = {
                    "price": final_price,
                    "url": cached_url,
                    "in_stock": direct_match["in_stock"],
                    "available": True,
                    "verified": True
                }
                print(f"[Hybrid Scraper] Successfully verified cached URL for {pname}. Price: {final_price}")
            else:
                print(f"[Hybrid Scraper] Direct page verification failed or blocked for cached URL of {pname}. Falling back to search.")
                platforms_to_search.append(pname)
        else:
            platforms_to_search.append(pname)
    if platforms_to_search:
        import asyncio
        yield f"data: {json.dumps({'status': 'started', 'message': f'Launching parallel direct Crawl4AI scraping for {len(platforms_to_search)} platforms...'})}\n\n"
        
        # Build search URLs for the platforms to search
        search_urls = build_platform_urls(product_name, brand)
        
        # Prepare async scraping tasks
        tasks = []
        match_keywords = [w for w in product_name.split() if len(w) > 2]
        
        for pname in platforms_to_search:
            surl = search_urls.get(pname)
            if not surl:
                continue
            
            task = scrape_platform_with_crawl4ai(
                platform_name=pname,
                search_url=surl,
                brand=brand,
                match_keywords=match_keywords,
                baseline_price=baseline_price_inr,
                description=description
            )
            tasks.append((pname, task))
            
        if tasks:
            pnames = [t[0] for t in tasks]
            coroutines = [t[1] for t in tasks]
            
            yield f"data: {json.dumps({'status': 'started', 'message': f'Crawling {pnames} directly in parallel with Playwright stealth browser...'})}\n\n"
            
            results = await asyncio.gather(*coroutines, return_exceptions=True)
            
            for pname, res in zip(pnames, results):
                if isinstance(res, Exception):
                    print(f"[Direct Scraper] Error crawling {pname}: {res}")
                    continue
                if res and isinstance(res, dict):
                    price = float(res.get("price_inr", 0))
                    url = res.get("url", "")
                    if price > 0 and url:
                        # Direct metadata verification (double checking)
                        direct_match = verify_direct_page_price(url, pname)
                        if direct_match:
                            final_price = direct_match["price"]
                            if direct_match["currency"] == "USD":
                                final_price = round(final_price * 83.3, 2)
                            extracted[pname] = {
                                "price": final_price,
                                "url": url,
                                "in_stock": direct_match["in_stock"],
                                "available": True,
                                "verified": True
                            }
                            print(f"[Direct Scraper] Verified crawled page for {pname} live. Price: {final_price}")
                        else:
                            # Convert currency to INR if USD in case of direct fallback
                            is_usd = pname in ("Walmart", "Ebay", "BestBuy", "Target")
                            final_price = round(price * 83.3, 2) if is_usd else price
                            extracted[pname] = {
                                "price": final_price,
                                "url": url,
                                "in_stock": True,
                                "available": True,
                                "verified": False
                            }
                            print(f"[Direct Scraper] Match Crawl4AI fallback for {pname}. Price: {final_price}")
                
    # 4. Format and yield results
    for pname, pconfig in pconfigs.items():
        pdata = extracted.get(pname, {})
        price = float(pdata.get("price", 0))
        url = pdata.get("url", "")
        
        # Skip if price wasn't found
        if price <= 0:
            continue
            
        method = "Live Crawl4AI (Verified)" if pdata.get("verified") else "Live Crawl4AI"
        price_gap_pct = round(((price - baseline_price_inr) / baseline_price_inr) * 100, 1) if baseline_price_inr > 0 else 0.0
        
        result = {
            "platform_name": pname,
            "platform_icon": pconfig["icon"],
            "platform_color": pconfig["color"],
            "price": price,
            "currency": "INR",
            "price_usd": round(price / 83.3, 2),
            "price_gap_pct": price_gap_pct,
            "in_stock": pdata.get("in_stock", True),
            "available": True,
            "url": url,
            "fetch_method": method
        }
        
        # Yield SSE format
        yield f"data: {json.dumps({'status': 'success', 'data': result})}\n\n"
        
    yield f"data: {json.dumps({'status': 'completed'})}\n\n"


async def fetch_multi_platform_prices(
    search_query: str = None,
    brand: str = "",
    category: str = "",
    baseline_price_inr: float = 0,
    barcode: str = "",
    description: str = "",
    product_id: str = None,
    **kwargs
) -> dict:
    """Non-streaming wrapper over stream_multi_platform_prices for backwards compatibility."""
    q = search_query or kwargs.get("product_name") or ""
    price = baseline_price_inr or kwargs.get("baseline_price_usd") or 0.0
    
    final = {}
    async for chunk in stream_multi_platform_prices(
        search_query=q,
        brand=brand,
        category=category,
        baseline_price_inr=price,
        barcode=barcode,
        description=description,
        product_id=product_id
    ):
        if not chunk.startswith("data: "):
            continue
        try:
            data_str = chunk[6:].strip()
            data = json.loads(data_str)
            if data.get("status") == "success" and "data" in data:
                pdata = data["data"]
                pname = pdata["platform_name"]
                final[pname] = pdata
        except Exception as e:
            print(f"[fetch_multi_platform_prices wrapper] Error: {e}")
    return final
