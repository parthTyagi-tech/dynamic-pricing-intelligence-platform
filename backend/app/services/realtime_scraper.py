import re
import json
import os
import random
import re
import requests
from datetime import datetime, timezone
from urllib.parse import quote_plus
from app.services.ai.client import async_structured_json_completion


# ─────────────────────────────────────────────────────────
# Platform Configuration
# ─────────────────────────────────────────────────────────

PLATFORMS = [
    {"name": "Amazon", "icon": "Az", "color": "#FF9900", "search_url": "https://www.amazon.in/s?k={query}", "currency": "INR"},
    {"name": "Flipkart", "icon": "FK", "color": "#2874F0", "search_url": "https://www.flipkart.com/search?q={query}", "currency": "INR"},
    {"name": "Ajio", "icon": "AJ", "color": "#F472B6", "search_url": "https://www.ajio.com/search/?text={query}", "currency": "INR"},
    {"name": "Croma", "icon": "CR", "color": "#34D399", "search_url": "https://www.croma.com/searchB?q={query}", "currency": "INR"},
    {"name": "Myntra", "icon": "MY", "color": "#FB7185", "search_url": "https://www.myntra.com/{query}", "currency": "INR"},
    {"name": "Nykaa", "icon": "NK", "color": "#F9A8D4", "search_url": "https://www.nykaa.com/search/result/?q={query}", "currency": "INR"},
    {"name": "Reliance Digital", "icon": "RD", "color": "#A78BFA", "search_url": "https://www.reliancedigital.in/search?q={query}", "currency": "INR"},
    {"name": "Tata CLiQ", "icon": "TC", "color": "#C084FC", "search_url": "https://www.tatacliq.com/search/?searchCategory=all&searchText={query}", "currency": "INR"},
]

INR_TO_USD = 83.3

MULTI_PLATFORM_SYSTEM = """You are an e-commerce market intelligence agent.
Given a product name, brand, category, barcode (if available), and the seller's own price in INR, you must estimate realistic current market prices across multiple e-commerce platforms.

IMPORTANT RULES:
- Return prices STRICTLY in INR (₹) for ALL platforms.
- You MUST multiply US Dollar amounts by 83.3 to get the INR price for US platforms like Walmart, Shopify, and Brand Website. DO NOT output $194 as 194 INR; it must be ~16000 INR.
- All returned prices MUST be within ±5-15% of the seller's INR price.
- If a product category doesn't match a platform (e.g., electronics on Myntra which is fashion-only), set "available" to false and price to 0.
- Be realistic: marketplace pricing varies by category and channel. Use the barcode (EAN/UPC) if provided to assume highly accurate matched pricing.

Return ONLY valid JSON with this exact structure:
{
  "Amazon": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Flipkart": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Ajio": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Croma": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Myntra": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Nykaa": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Reliance Digital": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>},
  "Tata CLiQ": {"price": <float>, "currency": "INR", "in_stock": <bool>, "available": <bool>}
}
"""


# ─────────────────────────────────────────────────────────
# Amazon Real-time Scraper (Mobile UA)
# ─────────────────────────────────────────────────────────

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
        from crawl4ai import AsyncWebCrawler, BrowserConfig
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
                            elif platform_name == "Croma": url = "https://www.croma.com" + url
                            elif platform_name == "Nykaa": url = "https://www.nykaa.com" + url
                            elif platform_name == "Reliance Digital": url = "https://www.reliancedigital.in" + url
                            elif platform_name == "Tata CLiQ": url = "https://www.tatacliq.com" + url
                        
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
        "Ajio": {"price": round(baseline_inr * random.uniform(0.85, 0.98), 2) if is_fashion else 0, "currency": "INR", "in_stock": is_fashion, "available": is_fashion},
        "Croma": {"price": round(baseline_inr * random.uniform(0.94, 1.06), 2) if not is_fashion else 0, "currency": "INR", "in_stock": not is_fashion, "available": not is_fashion},
        "Myntra": {"price": round(baseline_inr * random.uniform(0.88, 1.02), 2) if is_fashion else 0, "currency": "INR", "in_stock": is_fashion, "available": is_fashion},
        "Nykaa": {"price": round(baseline_inr * random.uniform(0.90, 1.04), 2) if category in ("beauty", "personal care") else 0, "currency": "INR", "in_stock": category in ("beauty", "personal care"), "available": category in ("beauty", "personal care")},
        "Reliance Digital": {"price": round(baseline_inr * random.uniform(0.93, 1.07), 2) if not is_fashion else 0, "currency": "INR", "in_stock": not is_fashion, "available": not is_fashion},
        "Tata CLiQ": {"price": round(baseline_inr * random.uniform(0.92, 1.08), 2), "currency": "INR", "in_stock": True, "available": True},
    }


def normalize_price(value, currency: str = "INR") -> float:
    """Normalize marketplace price strings into a clean INR float."""
    if value is None:
        return 0.0
    raw = str(value).strip().replace("₹", "").replace(",", "").replace(" ", " ")
    numbers = re.findall(r"\d+(?:\.\d+)?", raw)
    if not numbers:
        return 0.0
    price = float(numbers[0])
    code = (currency or "INR").upper()
    if code in {"USD", "$"} or "$" in str(value):
        price *= INR_TO_USD
    elif code in {"EUR", "€"} or "€" in str(value):
        price *= 90.0
    elif code in {"GBP", "£"} or "£" in str(value):
        price *= 105.0
    return round(price, 2)


def extract_price_from_html(html: str) -> dict | None:
    """Extract a product price using structured data, metadata, then resilient text fallback."""
    import json
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html or "", "html.parser")
    # Strategy A: JSON-LD / Schema.org offers.
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(script.string or script.get_text() or "")
            candidates = payload if isinstance(payload, list) else [payload]
            expanded = []
            for candidate in candidates:
                expanded.append(candidate)
                expanded.extend(candidate.get("@graph", []) if isinstance(candidate, dict) else [])
            for candidate in expanded:
                if not isinstance(candidate, dict):
                    continue
                offers = candidate.get("offers")
                offers = offers[0] if isinstance(offers, list) and offers else offers
                if isinstance(offers, dict) and offers.get("price") is not None:
                    price = normalize_price(offers.get("price"), offers.get("priceCurrency", "INR"))
                    if price > 0:
                        availability = str(offers.get("availability", "")).lower()
                        return {"price": price, "currency": "INR", "in_stock": "outofstock" not in availability and "discontinued" not in availability, "extraction_strategy": "jsonld"}
        except (ValueError, TypeError, json.JSONDecodeError):
            continue

    # Strategy A/B: OpenGraph, product meta, and common price attributes.
    price_meta = soup.find("meta", attrs={"property": re.compile(r"(?:og:price:amount|product:price:amount|twitter:price:amount)", re.I)}) or soup.find("meta", attrs={"name": re.compile(r"(?:price|amount)", re.I)})
    if price_meta and price_meta.get("content"):
        currency_meta = soup.find("meta", attrs={"property": re.compile(r"(?:og:price:currency|product:price:currency|twitter:price:currency)", re.I)}) or soup.find("meta", attrs={"name": re.compile(r"currency", re.I)})
        currency = currency_meta.get("content", "INR") if currency_meta else "INR"
        price = normalize_price(price_meta.get("content"), currency)
        if price > 0:
            availability = " ".join(tag.get("content", "") for tag in soup.find_all("meta") if "availability" in str(tag.get("property", "")).lower() or "availability" in str(tag.get("name", "")).lower()).lower()
            return {"price": price, "currency": "INR", "in_stock": "outofstock" not in availability, "extraction_strategy": "metadata"}

    # Strategy B/C: resilient DOM text and search-result snippet fallback.
    text = soup.get_text(" ", strip=True)
    patterns = [r"(?:₹|INR\s*)\s*([\d,]+(?:\.\d{1,2})?)", r"(?:\$|USD\s*)\s*([\d,]+(?:\.\d{1,2})?)", r"(?:price|mrp|now)\s*[:\-]?\s*([\d,]+(?:\.\d{1,2})?)"]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            currency = "USD" if "$" in match.group(0) or "USD" in match.group(0).upper() else "INR"
            price = normalize_price(match.group(1), currency)
            if price > 0:
                return {"price": price, "currency": "INR", "in_stock": "out of stock" not in text.lower(), "extraction_strategy": "dom_text"}
    return None


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

        # Run the shared deterministic extraction engine first; retain the legacy parser below as a compatibility fallback.
        extracted = extract_price_from_html(r.text)
        if extracted:
            print(f"[Direct Page Verifier] {extracted['extraction_strategy']}: {extracted['price']} INR")
            return extracted
        
        # Legacy compatibility fallback for platform-specific markup.
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
    product_id: str = None,
    platforms: list[str] | None = None,
):
    """
    Scrapes DuckDuckGo HTML results for the product across multiple storefront sites
    in a single request, then extracts structured prices and URLs using the LLM.
    Integrates cached direct URL checks and meta tag/JSON-LD verification to guarantee
    accuracy, freshness, and speed while minimizing search engine rate limit hits.
    """
    import requests
    import urllib.parse
    from bs4 import BeautifulSoup
    from app.services.ai.client import async_structured_json_completion
    
    product_name = search_query
    
    # 0. Set up targets configuration
    pconfigs = {
        "Amazon": {"icon": "Az", "color": "#FF9900", "domains": ["amazon.in", "amazon.com"]},
        "Flipkart": {"icon": "FK", "color": "#2874F0", "domains": ["flipkart.com"]},
        "Ajio": {"icon": "AJ", "color": "#F472B6", "domains": ["ajio.com"]},
        "Croma": {"icon": "CR", "color": "#34D399", "domains": ["croma.com"]},
        "Myntra": {"icon": "MY", "color": "#FB7185", "domains": ["myntra.com"]},
        "Nykaa": {"icon": "NK", "color": "#F9A8D4", "domains": ["nykaa.com"]},
        "Reliance Digital": {"icon": "RD", "color": "#A78BFA", "domains": ["reliancedigital.in"]},
        "Tata CLiQ": {"icon": "TC", "color": "#C084FC", "domains": ["tatacliq.com"]}
    }
    if platforms:
        requested = {name.strip() for name in platforms}
        pconfigs = {name: config for name, config in pconfigs.items() if name in requested}

    # Deterministic demo mode: return clearly labelled sample evidence without
    # pretending it was fetched from a live marketplace.
    if os.environ.get("MOCK_SCRAPER", "false").lower() == "true":
        now = datetime.now(timezone.utc).isoformat()
        search_urls = build_platform_urls(product_name, brand)
        for index, (pname, pconfig) in enumerate(pconfigs.items()):
            yield f"data: {json.dumps({'status': 'started', 'platform': pname, 'message': f'Mock scraper started for {pname}.'})}\n\n"
            factor = 0.96 + ((index % 3) * 0.02)
            price = round(float(baseline_price_inr or 0) * factor, 2)
            result = {
                "platform_name": pname,
                "platform_icon": pconfig["icon"],
                "platform_color": pconfig["color"],
                "price": price,
                "currency": "INR",
                "price_usd": round(price / INR_TO_USD, 2) if price else 0,
                "price_gap_pct": round(((price - baseline_price_inr) / baseline_price_inr) * 100, 1) if baseline_price_inr else 0.0,
                "in_stock": True,
                "available": price > 0,
                "url": search_urls.get(pname, ""),
                "fetch_method": "Mock fixture",
                "scraped_at": now,
            }
            yield f"data: {json.dumps({'status': 'success', 'platform': pname, 'data': result})}\n\n"
        yield f"data: {json.dumps({'status': 'completed', 'mock': True, 'scraped_at': now})}\n\n"
        return

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
    # 2. Pass 1: DuckDuckGo Aggregator (Fast & Light Search Engine Scraper)
    listings = []
    if platforms_to_search:
        yield f"data: {json.dumps({'status': 'started', 'message': f'Pass 1: Searching aggregator for {len(platforms_to_search)} platforms...'})}\n\n"
        
        # Build optimized query targeting only the required platforms
        site_filters = []
        for pname in platforms_to_search:
            for dom in pconfigs[pname]["domains"]:
                site_filters.append(f"site:{dom}")
                
        platforms_query = " OR ".join(site_filters)
        query_clean = product_name.strip()
        brand_clean = brand.strip() if brand else ""
        if brand_clean and not query_clean.lower().startswith(brand_clean.lower()):
            query_clean = f"{brand_clean} {query_clean}"
        full_query = f"{query_clean} price ({platforms_query})"
        
        url = "https://lite.duckduckgo.com/lite/"
        data = {"q": full_query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        try:
            r = requests.post(url, data=data, headers=headers, timeout=12)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                for a in soup.find_all('a', class_='result-link'):
                    title = a.text.strip()
                    href = a['href']
                    if "duckduckgo.com/y.js" in href:
                        continue
                    
                    parent_tr = a.find_parent('tr')
                    snippet = ""
                    if parent_tr:
                        next_tr = parent_tr.find_next_sibling('tr')
                        if next_tr:
                            snippet_td = next_tr.find('td', class_='result-snippet')
                            if snippet_td:
                                snippet = snippet_td.text.strip()
                    listings.append({
                        "title": title,
                        "url": href,
                        "snippet": snippet
                    })
        except Exception as e:
            print(f"[DDG Aggregator] Fetch error: {e}")
            
        if listings:
            yield f"data: {json.dumps({'status': 'started', 'message': f'Pass 1: Analyzing {len(listings)} matching listings with AI...'})}\n\n"
            try:
                system_prompt = f"""You are an expert e-commerce pricing intelligence analyzer.
Your task is to analyze a list of search engine results (titles, urls, snippets) for a target product, and extract the matching product prices in INR (₹) and the direct product URL for each of the requested platforms.

Platforms to extract:
{", ".join(platforms_to_search)}

CRITICAL CONVERSION & SELECTION RULES:
1. Prices MUST be in INR (₹).
2. If the price in the snippet is in USD ($), you MUST multiply it by 83.3 to get the price in INR. (e.g., $999.00 -> 83216.70).
3. If no price is mentioned for a platform, or the product is not found, set "price" to 0 and "in_stock" to false.
4. Extract the exact product URL (not the general category/search page) if available in the listings.
5. Only select listings that match the target product model, storage size, RAM, and exact details. DO NOT match variants, base models if looking for Pro, refurbished/used unless specified, or carrier-locked versions.

Return ONLY a JSON object with this exact structure:
{{
""" + "\n".join([f'  "{p}": {{"price": <float>, "url": "<url>", "in_stock": <bool>, "available": <bool>}},' for p in platforms_to_search])[:-1] + """
}
"""
                user_prompt = f"""Target Product:
Name: {product_name}
Brand: {brand}
Baseline Price: {baseline_price_inr} INR
Description: {description}

Search Listings:
{json.dumps(listings, indent=2)}
"""
                res = await async_structured_json_completion(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    agent_name="ScraperExtractionAgent"
                )
                if res:
                    for pname, pdata in res.items():
                        price = float(pdata.get("price", 0))
                        url = pdata.get("url", "").strip()
                        if url:
                            # Try to verify the LLM's extracted URL live (Metadata Verification)
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
                                print(f"[Pass 1] Verified extracted URL for {pname} live. Price: {final_price}")
                            elif price > 0:
                                is_usd = False
                                final_price = round(price * 83.3, 2) if is_usd else price
                                extracted[pname] = {
                                    "price": final_price,
                                    "url": url,
                                    "in_stock": pdata.get("in_stock", True),
                                    "available": True,
                                    "verified": False
                                }
                                print(f"[Pass 1] Live verification failed for {pname}, keeping snippet price: {final_price}")
                        elif price > 0:
                            is_usd = False
                            final_price = round(price * 83.3, 2) if is_usd else price
                            extracted[pname] = {
                                "price": final_price,
                                "url": "",
                                "in_stock": pdata.get("in_stock", True),
                                "available": True,
                                "verified": False
                            }
            except Exception as e:
                print(f"[Pass 1 AI extraction] Error: {e}")

    # 3. Pass 2: Parallel Crawl4AI Direct Platform Scraping (for platforms that failed in Pass 1)
    failed_platforms = [p for p in platforms_to_search if p not in extracted or float(extracted[p].get("price", 0)) <= 0]
    
    if failed_platforms:
        import asyncio
        yield f"data: {json.dumps({'status': 'started', 'message': f'Pass 2: Launching background Crawl4AI browser scraping for {len(failed_platforms)} failed platforms...'})}\n\n"
        
        # Build search URLs for the platforms to search
        search_urls = build_platform_urls(product_name, brand)
        
        # Prepare async scraping tasks
        tasks = []
        match_keywords = [w for w in product_name.split() if len(w) > 2]
        
        for pname in failed_platforms:
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
            
            # Execute tasks in parallel if running on a high-memory environment (e.g. Google Cloud Run)
            parallel_crawling = os.environ.get("PARALLEL_CRAWLING", "false").lower() == "true"
            
            if parallel_crawling:
                yield f"data: {json.dumps({'status': 'started', 'message': f'Crawling {len(coroutines)} platforms in parallel with Playwright stealth browsers...'})}\n\n"
                results = await asyncio.gather(*coroutines, return_exceptions=True)
                for pname, res in zip(pnames, results):
                    if isinstance(res, Exception):
                        print(f"[Pass 2] Error crawling {pname}: {res}")
                        continue
                    if res and isinstance(res, dict):
                        price = float(res.get("price_inr", 0))
                        url = res.get("url", "")
                        if price > 0 and url:
                            try:
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
                                    print(f"[Pass 2] Verified crawled page for {pname} live. Price: {final_price}")
                                else:
                                    # Convert currency to INR if USD in case of direct fallback
                                    is_usd = False
                                    final_price = round(price * 83.3, 2) if is_usd else price
                                    extracted[pname] = {
                                        "price": final_price,
                                        "url": url,
                                        "in_stock": True,
                                        "available": True,
                                        "verified": False
                                    }
                                    print(f"[Pass 2] Match Crawl4AI fallback for {pname}. Price: {final_price}")
                            except Exception as e:
                                print(f"[Pass 2] Exception during parsing of {pname}: {e}")
            else:
                # Execute tasks sequentially rather than in parallel to keep memory usage under Render 512MB RAM limit (avoiding OOM/SIGKILL)
                for pname, coroutine in zip(pnames, coroutines):
                    yield f"data: {json.dumps({'status': 'started', 'message': f'Crawling {pname} directly with Playwright stealth browser...'})}\n\n"
                    try:
                        res = await coroutine
                        if isinstance(res, Exception):
                            print(f"[Pass 2] Error crawling {pname}: {res}")
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
                                    print(f"[Pass 2] Verified crawled page for {pname} live. Price: {final_price}")
                                else:
                                    # Convert currency to INR if USD in case of direct fallback
                                    is_usd = False
                                    final_price = round(price * 83.3, 2) if is_usd else price
                                    extracted[pname] = {
                                        "price": final_price,
                                        "url": url,
                                        "in_stock": True,
                                        "available": True,
                                        "verified": False
                                    }
                                    print(f"[Pass 2] Match Crawl4AI fallback for {pname}. Price: {final_price}")
                    except Exception as e:
                        print(f"[Pass 2] Exception during crawling of {pname}: {e}")
                
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
            "fetch_method": method,
            "scraped_at": datetime.now(timezone.utc).isoformat()
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
    platforms: list[str] | None = None,
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
        product_id=product_id,
        platforms=platforms,
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
