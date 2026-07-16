import asyncio
import sys
import os

# Add backend to sys.path
sys.path.append(r"d:\1.Projects\Klypup Project\backend")

from app.services.realtime_scraper import stream_multi_platform_prices

async def test():
    async for chunk in stream_multi_platform_prices(
        search_query="iPhone 15 (128GB)",
        brand="Apple",
        category="electronics",
        baseline_price_inr=79900.0,
        barcode="",
        description="Apple iPhone 15. Base model, not Pro or Plus. Color: Black. Storage: 128GB. A16 Bionic chip, Dynamic Island. Do NOT match with iPhone 15 Pro, iPhone 15 Plus, or iPhone 15 Pro Max."
    ):
        print(chunk)

if __name__ == "__main__":
    asyncio.run(test())
