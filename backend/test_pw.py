import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to Myntra...")
        await page.goto('https://www.myntra.com/nike-revolution-7', wait_until='networkidle')
        print("Waiting for products...")
        try:
            await page.wait_for_selector('.product-base', timeout=5000)
        except:
            print("Timeout waiting for .product-base")
        html = await page.content()
        print("HTML length:", len(html))
        
        # Check if product-base exists
        if "product-base" in html:
            print("FOUND PRODUCTS!")
        else:
            print("NO PRODUCTS FOUND!")
        await browser.close()

if __name__ == '__main__':
    asyncio.run(run())
