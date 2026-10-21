import asyncio
import json
import re
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}

async def verify_amazon():
    print("\n--- [AMAZON PDP VERIFICATION] ---")
    url = "https://www.amazon.in/dp/B071Z8M4KX"
    async with AsyncSession(impersonate="chrome124") as s:
        r = await s.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        title_node = soup.select_one("#productTitle")
        title = title_node.get_text(strip=True) if title_node else "N/A"
        # Core price elements on Amazon PDP
        price_whole = soup.select_one("span.a-price-whole")
        price_val = price_whole.get_text(strip=True) if price_whole else "N/A"
        apex_price = soup.select_one("span.apexPriceToPay span.a-offscreen")
        apex_val = apex_price.get_text(strip=True) if apex_price else "N/A"
        mrp_node = soup.select_one("span.a-price.a-text-price span.a-offscreen")
        mrp_val = mrp_node.get_text(strip=True) if mrp_node else "N/A"
        print(f"URL: {url}")
        print(f"Title: '{title}'")
        print(f"price-whole: '{price_val}'")
        print(f"apexPriceToPay (offscreen): '{apex_val}'")
        print(f"MRP (offscreen strike):     '{mrp_val}'")

if __name__ == "__main__":
    asyncio.run(verify_amazon())
