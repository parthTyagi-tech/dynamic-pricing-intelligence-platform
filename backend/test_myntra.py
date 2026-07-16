import asyncio
import sys

sys.path.append(r"d:\1.Projects\Klypup Project\backend")
from crawl4ai import AsyncWebCrawler, BrowserConfig

async def test():
    browser_config = BrowserConfig(
        headless=True,
        enable_stealth=True,
        user_agent_mode="random",
    )
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://html.duckduckgo.com/html/?q=site:walmart.com+Nike+Revolution+7+price",
        )
        print("MARKDOWN:")
        print(result.markdown[:2000])

if __name__ == "__main__":
    asyncio.run(test())
