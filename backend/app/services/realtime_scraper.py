import random
from app.services.ai.client import async_structured_json_completion

REALTIME_SCRAPER_SYSTEM = """You are a real-time e-commerce price scraping assistant.
Given a product name and its current price, you must output realistic, current competitor data for Amazon, Flipkart, and Walmart.
Return a structured JSON object containing only the keys: "Amazon", "Flipkart", and "Walmart", with each value being an object containing "price" (float) and "in_stock" (boolean).
"""

def _get_fallback_prices(current_price: float) -> dict:
    """Safe mathematical fallback for competitor prices when the LLM fails."""
    # 20% chance a competitor is out of stock to test Phase 2
    return {
        "Amazon": {"price": round(current_price * random.uniform(0.92, 1.05), 2), "in_stock": random.random() > 0.2},
        "Flipkart": {"price": round(current_price * random.uniform(0.90, 1.03), 2), "in_stock": random.random() > 0.2},
        "Walmart": {"price": round(current_price * random.uniform(0.91, 1.04), 2), "in_stock": random.random() > 0.2}
    }

async def fetch_realtime_competitor_prices(product_name: str, current_price: float) -> dict:
    """
    Simulates real-time scraping of competitor prices from Amazon, Flipkart, and Walmart.
    Uses LLM JSON completion to generate realistic, context-aware competitor prices.
    Falls back to mathematical offsets if the LLM call fails.
    """
    user_prompt = f"""Fetch current competitor prices for:
Product Name: {product_name}
Current Catalog Price: ${current_price:.2f}

Format JSON response exactly as:
{{
  "Amazon": {{"price": <float>, "in_stock": <boolean>}},
  "Flipkart": {{"price": <float>, "in_stock": <boolean>}},
  "Walmart": {{"price": <float>, "in_stock": <boolean>}}
}}
"""
    try:
        result = await async_structured_json_completion(
            system_prompt=REALTIME_SCRAPER_SYSTEM,
            user_prompt=user_prompt,
            agent_name="RealtimeScraperAgent"
        )
        if result and all(k in result for k in ["Amazon", "Flipkart", "Walmart"]):
            validated = {}
            for k in ["Amazon", "Flipkart", "Walmart"]:
                validated[k] = {
                    "price": round(float(result[k]["price"]), 2),
                    "in_stock": bool(result[k]["in_stock"])
                }
            return validated
    except Exception as e:
        print(f"[Realtime Scraper] Error fetching prices via LLM: {e}")
    
    return _get_fallback_prices(current_price)
