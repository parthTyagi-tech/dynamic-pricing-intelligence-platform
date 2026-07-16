import asyncio
import sys

sys.path.append(r"d:\1.Projects\Klypup Project\backend")
from app.services.realtime_scraper import stream_multi_platform_prices

async def test():
    async for chunk in stream_multi_platform_prices(
        product_name="Nike Men Revolution 7 Running Shoes",
        brand="Nike",
        category="fashion",
        baseline_price_inr=3500.0,
        barcode="",
        description=""
    ):
        print(chunk)

if __name__ == "__main__":
    asyncio.run(test())
