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

async def verify_flipkart():
    print("\n--- [FLIPKART PDP VERIFICATION] ---")
    url = "https://www.flipkart.com/boat-bassheads-100-wired-earphones/p/itm3f39544d0b96c"
    async with AsyncSession(impersonate="chrome124") as s:
        r = await s.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        # Flipkart PDP price selectors
        price_node = soup.select_one("div.Nx9bqj.CxhGGd, div._30jeq3._16Jk6d, div.Nx9bqj")
        mrp_node = soup.select_one("div.yRaY8j.A68aKn, div._3I9_wc._2p6cR8, div.yRaY8j")
        # Also check JSON-LD Schema
        json_ld_price = None
        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(tag.string)
                if isinstance(data, list):
                    data = data[0]
                offers = data.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0]
                if "price" in offers:
                    json_ld_price = offers["price"]
            except Exception:
                pass
        print(f"URL: {url}")
        print(f"HTML Price Text: '{price_node.get_text(strip=True) if price_node else 'N/A'}'")
        print(f"HTML MRP Text:   '{mrp_node.get_text(strip=True) if mrp_node else 'N/A'}'")
        print(f"Schema.org Price: {json_ld_price}")

async def verify_scooboo():
    print("\n--- [SCOOBOO PDP VERIFICATION] ---")
    url = "https://scooboo.in/products/tombow-airpress-pressurized-ballpoint-pen.json"
    async with AsyncSession(impersonate="chrome124") as s:
        r = await s.get(url, headers=headers, timeout=15)
        data = r.json()
        p = data.get("product", {})
        variants = p.get("variants", [])
        print(f"URL: https://scooboo.in/products/tombow-airpress-pressurized-ballpoint-pen")
        print(f"Product Title: '{p.get('title')}'")
        for i, v in enumerate(variants[:3]):
            print(f"Variant {i} ('{v.get('title')}'): price={v.get('price')} (paise/INR), compare_at_price (MRP)={v.get('compare_at_price')}, available={v.get('available')}")

async def verify_croma():
    print("\n--- [CROMA API VERIFICATION] ---")
    api_url = "https://api.croma.com/searchservices/v1/search?currentPage=0&query=Sony+WH-1000XM5%3Arelevance&fields=FULL&channel=WEB&channelCode=400049"
    croma_headers = {
        "Origin": "https://www.croma.com",
        "Referer": "https://www.croma.com/",
        "Accept": "application/json",
        "csc-channel": "WEB",
        "User-Agent": headers["User-Agent"]
    }
    async with AsyncSession(impersonate="chrome124") as s:
        r = await s.get(api_url, headers=croma_headers, timeout=15)
        data = r.json()
        products = data.get("products", [])
        if products:
            p0 = products[0]
            name = p0.get("name")
            p_val = p0.get("price", {}).get("value")
            m_val = p0.get("mrp", {}).get("value")
            p_code = p0.get("code")
            print(f"Product: '{name}'")
            print(f"Raw API price.value: {p_val}")
            print(f"Raw API mrp.value:   {m_val}")
            print(f"Product Code / PDP:  https://www.croma.com/p/{p_code}")

async def verify_myntra():
    print("\n--- [MYNTRA PDP VERIFICATION] ---")
    slug = "roadster-men-solid-pure-cotton-t-shirt"
    search_url = f"https://www.myntra.com/{slug}"
    async with AsyncSession(impersonate="chrome124") as s:
        r = await s.get(search_url, headers=headers, timeout=15)
        idx = r.text.find("window.__myx = ")
        if idx != -1:
            raw = r.text[idx + len("window.__myx = "):]
            end = raw.find("</script>")
            clean_json = raw[:end].strip().rstrip(";")
            data = json.loads(clean_json)
            products = data.get("searchData", {}).get("results", {}).get("products", [])
            if products:
                p0 = products[0]
                print(f"Product: '{p0.get('brand')} {p0.get('productName')}'")
                print(f"Raw JSON price: {p0.get('price')} (INR)")
                print(f"Raw JSON mrp:   {p0.get('mrp')} (INR)")
                print(f"Landing URL:    https://www.myntra.com/{p0.get('landingPageUrl')}")

async def main():
    await verify_flipkart()
    await verify_scooboo()
    await verify_croma()
    await verify_myntra()

if __name__ == "__main__":
    asyncio.run(main())
