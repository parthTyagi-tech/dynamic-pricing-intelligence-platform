import os
import sys

# Configure UTF-8 encoding for standard output and error across all operating systems
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import asyncio
from datetime import datetime, timezone

os.environ["MOCK_SCRAPING"] = "false"

from run import app
from app.extensions import db
from app.models.scraper_reliability import ScraperReliability, CircuitState
from app.services.agentic.scrapers.platform_scrapers import (
    AmazonScraperAgent,
    ScoobooScraperAgent,
    FlipkartScraperAgent,
    BlinkitScraperAgent,
    MyntraScraperAgent,
)
from app.services.agentic.supervisor_agent import SupervisorAgent


def reset_circuit(platform_name: str):
    """Ensure platform starts with clean CLOSED circuit breaker state."""
    rel = ScraperReliability.query.filter_by(platform=platform_name).first()
    if not rel:
        rel = ScraperReliability(platform=platform_name)
        db.session.add(rel)
    rel.circuit_state = CircuitState.CLOSED
    rel.failure_count_last_hour = 0
    rel.circuit_opened_at = None
    rel.last_failure_reason = None
    db.session.commit()


def main():
    app.config["MOCK_SCRAPING"] = False
    with app.app_context():
        db.create_all()

        # Ensure circuits are closed prior to live verification
        for p in ["Scooboo", "Amazon.in", "Flipkart", "Blinkit", "Myntra"]:
            reset_circuit(p)

        print("\n=======================================================")
        print("STAGE 1: LIVE STATIONERY EXTRACTION (SCOOBOO & AMAZON)")
        print("=======================================================")
        prod_stationery = {
            "id": "test-tombow-pen",
            "name": "Tombow Airpress Pressurized Ballpoint Pen",
            "brand": "Tombow",
            "current_price": 1000.0,
            "cost_price": 700.0,
            "category": "stationery",
        }

        # 1. Scooboo Extraction
        res_sc = asyncio.run(ScoobooScraperAgent().scrape("task-sc", prod_stationery, "org-1"))
        print(f"Scooboo Status: {res_sc.get('status')}")
        print(f"Scooboo Price: INR {res_sc.get('price')}, Title: {res_sc.get('product_title')}, URL: {res_sc.get('product_url')}")
        assert res_sc.get("status") == "success", f"Scooboo failed: {res_sc}"
        assert res_sc.get("price") == 1113.0, f"Expected 1113.0, got {res_sc.get('price')}"
        assert res_sc.get("match_score", 0) >= 0.70, "Scooboo match score must be >= 0.70"
        assert "scooboo.in/products/" in res_sc.get("product_url", ""), "Must be real Scooboo product URL"
        print("--> Scooboo Live Extraction PASSED.")

        # 2. Amazon.in Extraction
        res_amz = asyncio.run(AmazonScraperAgent().scrape("task-amz", prod_stationery, "org-1"))
        print(f"Amazon Status: {res_amz.get('status')}")
        print(f"Amazon Price: INR {res_amz.get('price')}, Title: {res_amz.get('product_title')}, URL: {res_amz.get('product_url')}")
        assert res_amz.get("status") == "success", f"Amazon failed: {res_amz}"
        assert abs(float(res_amz.get("price", 0)) - 1000.0) <= 150.0, f"Amazon price {res_amz.get('price')} outside expected variance"
        assert res_amz.get("match_score", 0) >= 0.70, "Amazon match score must be >= 0.70"
        assert "amazon.in" in res_amz.get("product_url", ""), "Must be real Amazon URL"
        print("--> Amazon.in Live Extraction PASSED.")

        print("\n=======================================================")
        print("STAGE 2: LIVE ELECTRONICS EXTRACTION (FLIPKART)")
        print("=======================================================")
        prod_electronics = {
            "id": "test-boat-earphones",
            "name": "boAt BassHeads 100 Wired Earphones",
            "brand": "boAt",
            "current_price": 399.0,
            "cost_price": 250.0,
            "category": "electronics",
        }
        flipkart_agent = FlipkartScraperAgent()
        res_fk = asyncio.run(flipkart_agent.scrape("task-fk", prod_electronics, "org-1"))
        print(f"Flipkart Status: {res_fk.get('status')}")
        print(f"Flipkart Price: INR {res_fk.get('price')}, Title: {res_fk.get('product_title')}, URL: {res_fk.get('product_url')}")
        assert res_fk.get("status") == "success", f"Flipkart failed to extract live data: {res_fk}"
        assert float(res_fk.get("price", 0)) > 0, "Flipkart price must be > 0"
        assert res_fk.get("match_score", 0) >= 0.70, "Flipkart match score must be >= 0.70"
        assert "flipkart.com" in res_fk.get("product_url", ""), "Must be real Flipkart URL"
        print("--> Flipkart Live Extraction PASSED.")

        print("\n=======================================================")
        print("STAGE 3: LIVE QUICK-COMMERCE EXTRACTION (BLINKIT)")
        print("=======================================================")
        prod_grocery = {
            "id": "test-amul-milk",
            "name": "Amul Taaza Toned Milk",
            "brand": "Amul",
            "current_price": 54.0,
            "cost_price": 40.0,
            "category": "grocery",
        }
        blinkit_agent = BlinkitScraperAgent()
        res_bl = asyncio.run(blinkit_agent.scrape("task-bl", prod_grocery, "org-1"))
        print(f"Blinkit Status: {res_bl.get('status')}")
        print(f"Blinkit Price: INR {res_bl.get('price')}, Title: {res_bl.get('product_title')}, URL: {res_bl.get('product_url')}")
        assert res_bl.get("status") == "success", f"Blinkit failed to extract live data: {res_bl}"
        assert float(res_bl.get("price", 0)) > 0, "Blinkit price must be > 0"
        assert res_bl.get("match_score", 0) >= 0.70, "Blinkit match score must be >= 0.70"
        assert "blinkit.com" in res_bl.get("product_url", ""), "Must be real Blinkit URL"
        print("--> Blinkit Live Extraction PASSED.")

        print("\n=======================================================")
        print("STAGE 4: LIVE FASHION EXTRACTION (MYNTRA via curl_cffi)")
        print("=======================================================")
        prod_fashion = {
            "id": "test-roadster-tshirt",
            "name": "Roadster Men Solid Pure Cotton T-shirt",
            "brand": "Roadster",
            "current_price": 499.0,
            "cost_price": 250.0,
            "category": "fashion",
        }
        myntra_agent = MyntraScraperAgent()
        res_myntra = asyncio.run(myntra_agent.scrape("task-myntra", prod_fashion, "org-1"))
        print(f"Myntra Status: {res_myntra.get('status')}")
        print(f"Myntra Price: INR {res_myntra.get('price')}, Title: {res_myntra.get('product_title')}, URL: {res_myntra.get('product_url')}")
        assert res_myntra.get("status") == "success", f"Myntra failed to extract live data: {res_myntra}"
        assert float(res_myntra.get("price", 0)) > 0, "Myntra price must be > 0"
        assert res_myntra.get("match_score", 0) >= 0.70, "Myntra match score must be >= 0.70"
        assert "myntra.com" in res_myntra.get("product_url", ""), "Must be real Myntra URL"
        print("--> Myntra Live Extraction PASSED.")

        print("\n=======================================================")
        print("ALL LIVE MULTI-CATEGORY EXTRACTION STAGES PASSED (100% GREEN)")
        print("=======================================================\n")


if __name__ == "__main__":
    main()
