import asyncio
import sys
from crawl4ai import AsyncWebCrawler, BrowserConfig

async def main():
    browser_config = BrowserConfig(
        headless=True,
    )
    urls = {
        "Walmart": "https://html.duckduckgo.com/html/?q=site:walmart.com+Sony+WH-1000XM4+price",
        "Shopify": "https://html.duckduckgo.com/html/?q=Sony+WH-1000XM4+price+site:myshopify.com",
    }
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for name, url in urls.items():
            print(f"Fetching {name} from DDG...")
            try:
                result = await crawler.arun(url=url)
                print(f"{name} text length: {len(result.markdown)}")
                print(result.markdown[:500])
            except Exception as e:
                print(f"Error {name}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
