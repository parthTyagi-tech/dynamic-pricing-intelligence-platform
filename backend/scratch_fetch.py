import asyncio
import sys
from crawl4ai import AsyncWebCrawler, BrowserConfig

async def main():
    browser_config = BrowserConfig(
        headless=True,
        enable_stealth=True,
        user_agent_mode="random",
    )
    urls = {
        "Myntra": "https://www.myntra.com/sony",
        "Ajio": "https://www.ajio.com/search/?text=Sony%20WH-1000XM4",
        "Meesho": "https://www.meesho.com/search?q=Sony%20WH-1000XM4",
        "Walmart": "https://www.walmart.com/search?q=Sony+WH-1000XM4",
        "Shopify": "https://www.google.com/search?q=Sony+WH-1000XM4+site:myshopify.com",
    }
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for name, url in urls.items():
            print(f"Fetching {name}...")
            try:
                result = await crawler.arun(url=url)
                with open(f"{name}.html", "w", encoding="utf-8") as f:
                    f.write(result.html)
                print(f"{name} length: {len(result.html)}")
            except Exception as e:
                print(f"Error {name}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
