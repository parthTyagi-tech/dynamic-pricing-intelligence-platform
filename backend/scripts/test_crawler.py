import asyncio
import sys
import os

# Add backend directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.realtime_scraper import fetch_multi_platform_prices

async def main():
    print("Testing Crawl4AI Amazon Scraper (Phase 2)...")
    
    product_name = "iPhone 15 Pro Max"
    brand = "Apple"
    category = "electronics"
    baseline_price = 159900.0
    
    print(f"\nSearching for: {brand} {product_name}")
    print("This might take a few seconds as it launches a Playwright headless browser...\n")
    
    try:
        results = await fetch_multi_platform_prices(
            product_name=product_name,
            brand=brand,
            category=category,
            baseline_price_usd=baseline_price,
            barcode=""
        )
        
        print("Scrape Complete! Results:\n")
        
        for platform, data in results.items():
            print(f"[{platform}]")
            print(f"  Price: {data['currency']} {data['price']}")
            print(f"  In Stock: {data['in_stock']}")
            print(f"  URL: {data['url']}")
            print("-" * 30)
            
    except Exception as e:
        print(f"Error during scrape: {e}")

if __name__ == "__main__":
    asyncio.run(main())
