import os
import sys
import asyncio
import time

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

os.environ["FLASK_ENV"] = "testing"
os.environ["MOCK_SCRAPING"] = "false"

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from run import app
from app.extensions import db
from app.models.scraper_reliability import ScraperReliability, CircuitState
from app.services.agentic.scrapers.platform_scrapers import (
    AmazonScraperAgent,
    FlipkartScraperAgent,
    CromaScraperAgent,
    ScoobooScraperAgent,
    MyntraScraperAgent,
)

TEST_MATRIX = [
    {
        "platform": "Amazon.in",
        "agent": AmazonScraperAgent(),
        "products": [
            {
                "id": "amz-prod-1",
                "name": "Apple iPhone 15 (128 GB) - Black",
                "brand": "Apple",
                "current_price": 65000.0,
                "category": "electronics",
            },
            {
                "id": "amz-prod-2",
                "name": "boAt BassHeads 100 Wired Earphones",
                "brand": "boAt",
                "current_price": 399.0,
                "category": "electronics",
            },
            {
                "id": "amz-prod-3",
                "name": "Tombow Airpress Pressurized Ballpoint Pen",
                "brand": "Tombow",
                "current_price": 1000.0,
                "category": "stationery",
            },
        ],
    },
    {
        "platform": "Flipkart",
        "agent": FlipkartScraperAgent(),
        "products": [
            {
                "id": "fk-prod-1",
                "name": "boAt BassHeads 100 Wired Earphones",
                "brand": "boAt",
                "current_price": 399.0,
                "category": "electronics",
            },
            {
                "id": "fk-prod-2",
                "name": "Apple iPhone 15 (Black, 128 GB)",
                "brand": "Apple",
                "current_price": 65000.0,
                "category": "electronics",
            },
            {
                "id": "fk-prod-3",
                "name": "SAMSUNG Galaxy S24 5G (Onyx Black, 128 GB)",
                "brand": "SAMSUNG",
                "current_price": 65000.0,
                "category": "electronics",
            },
        ],
    },
    {
        "platform": "Croma",
        "agent": CromaScraperAgent(),
        "products": [
            {
                "id": "croma-prod-1",
                "name": "Sony WH-1000XM5 Noise Cancelling Headphones",
                "brand": "Sony",
                "current_price": 24990.0,
                "category": "electronics",
            },
            {
                "id": "croma-prod-2",
                "name": "Apple iPhone 15 (128GB, Black)",
                "brand": "Apple",
                "current_price": 65000.0,
                "category": "electronics",
            },
            {
                "id": "croma-prod-3",
                "name": "boAt Bassheads 100 In-Ear Wired Earphone with Mic",
                "brand": "boAt",
                "current_price": 399.0,
                "category": "electronics",
            },
        ],
    },
    {
        "platform": "Scooboo",
        "agent": ScoobooScraperAgent(),
        "products": [
            {
                "id": "sc-prod-1",
                "name": "Tombow Airpress Pressurized Ballpoint Pen",
                "brand": "Tombow",
                "current_price": 1000.0,
                "category": "stationery",
            },
            {
                "id": "sc-prod-2",
                "name": "Tombow Monograph Ballpoint Pen",
                "brand": "Tombow",
                "current_price": 300.0,
                "category": "stationery",
            },
            {
                "id": "sc-prod-3",
                "name": "Sakura Pigma Micron Pen",
                "brand": "Sakura",
                "current_price": 150.0,
                "category": "stationery",
            },
        ],
    },
    {
        "platform": "Myntra",
        "agent": MyntraScraperAgent(),
        "products": [
            {
                "id": "myn-prod-1",
                "name": "Roadster Men Solid Pure Cotton T-shirt",
                "brand": "Roadster",
                "current_price": 499.0,
                "category": "fashion",
            },
            {
                "id": "myn-prod-2",
                "name": "HRX by Hrithik Roshan Men Rapid Dry Active T-shirt",
                "brand": "HRX",
                "current_price": 599.0,
                "category": "fashion",
            },
            {
                "id": "myn-prod-3",
                "name": "Highlander Men Slim Fit Casual Shirt",
                "brand": "Highlander",
                "current_price": 699.0,
                "category": "fashion",
            },
        ],
    },
]

def reset_circuit(platform_name: str):
    rel = ScraperReliability.query.filter_by(platform=platform_name).first()
    if not rel:
        rel = ScraperReliability(platform=platform_name)
        db.session.add(rel)
    rel.circuit_state = CircuitState.CLOSED
    rel.failure_count_last_hour = 0
    rel.circuit_opened_at = None
    rel.last_failure_reason = None
    db.session.commit()

async def run_single_test(agent, prod, platform_name):
    print(f"\n[{platform_name}] Querying: '{prod['name']}' (Brand: {prod['brand']})...")
    start = time.perf_counter()
    try:
        res = await agent.scrape(f"audit-{prod['id']}", prod, "org-audit")
        duration = time.perf_counter() - start
        return {
            "platform": platform_name,
            "query": prod["name"],
            "status": res.get("status"),
            "price": res.get("price"),
            "mrp": res.get("mrp"),
            "title": res.get("product_title"),
            "url": res.get("product_url"),
            "score": res.get("match_score"),
            "mode": res.get("scrape_mode"),
            "reason": res.get("reason"),
            "duration_s": round(duration, 2),
        }
    except Exception as e:
        duration = time.perf_counter() - start
        return {
            "platform": platform_name,
            "query": prod["name"],
            "status": "exception",
            "price": None,
            "mrp": None,
            "title": None,
            "url": None,
            "score": 0.0,
            "mode": "error",
            "reason": str(e),
            "duration_s": round(duration, 2),
        }

def main():
    with app.app_context():
        db.create_all()
        for item in TEST_MATRIX:
            reset_circuit(item["platform"])

        results = []
        print("=" * 80)
        print("STARTING HONEST LIVE EXTRACTION AUDIT (5 PLATFORMS x 3 PRODUCTS = 15 LIVE CALLS)")
        print("MOCK_SCRAPING is FALSE. Real live network requests to all marketplaces.")
        print("=" * 80)

        for group in TEST_MATRIX:
            p_name = group["platform"]
            agent = group["agent"]
            for prod in group["products"]:
                res = asyncio.run(run_single_test(agent, prod, p_name))
                results.append(res)
                print(f"  -> Status: {res['status']} | Price: INR {res['price']} | Mode: {res['mode']} | Score: {res['score']} | Time: {res['duration_s']}s")
                if res['title']:
                    print(f"     Title: {res['title'][:65]}...")
                if res['url']:
                    print(f"     URL:   {res['url'][:80]}")
                # Brief polite pause to respect rate limits between requests
                time.sleep(1.5)

        print("\n" + "=" * 80)
        print("FINAL HONEST AUDIT SUMMARY TABLE")
        print("=" * 80)
        print(f"{'Platform':<10} | {'Status':<8} | {'Price (INR)':<11} | {'MRP (INR)':<10} | {'Score':<5} | {'Mode':<15} | {'Duration':<8} | {'Title'}")
        print("-" * 120)
        success_count = 0
        for r in results:
            p = str(r['price']) if r['price'] is not None else "N/A"
            m = str(r['mrp']) if r['mrp'] is not None else "N/A"
            t = (r['title'] or r.get('reason') or "N/A")[:35]
            if r['status'] == 'success':
                success_count += 1
            print(f"{r['platform']:<10} | {r['status']:<8} | {p:<11} | {m:<10} | {r['score']:<5} | {r['mode']:<15} | {r['duration_s']}s{'':<2} | {t}")

        print("=" * 80)
        print(f"AUDIT OUTCOME: {success_count} / {len(results)} PRODUCTS EXTRACTED SUCCESSFULLY FROM LIVE PLATFORMS.")
        print("=" * 80)

if __name__ == "__main__":
    main()
