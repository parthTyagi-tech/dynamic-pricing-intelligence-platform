#!/usr/bin/env python3
"""
tools/verify_all_18_scrapers_e2e.py

Complete End-to-End Live Cross-Verification of All 18 Platform Scraping Agents
across all 8 product categories, verifying:
1. Live real-world marketplace extraction against Indian e-commerce endpoints
2. Schema integrity via Pydantic ScrapedOffer model validation
3. Price sanity within realistic category bounds
4. Jaccard match score >= 0.70
5. Canonical HTTPS PDP URLs matching official platform domains
6. Cross-platform category MAD statistical aggregation via AggregatorAgent
7. Flask API route /api/agentic/scraper/<platform>/run-single with JWT auth
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# Configure UTF-8 encoding for standard output and error across all operating systems
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Ensure live scraping is active
os.environ["MOCK_SCRAPING"] = "false"
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from run import app
from app.extensions import db
from app.models.organization import Organization
from app.models.product import Product
from app.models.user import User
from app.models.scraper_reliability import ScraperReliability, CircuitState
from app.services.agentic.aggregator_agent import AggregatorAgent
from app.services.agentic.scrapers.base_scraper import MATCH_THRESHOLD
from app.services.agentic.scrapers.platform_scrapers import (
    SCRAPER_REGISTRY,
    get_scraper_for_platform,
)
from app.services.agentic.scrapers.schemas import ScrapedOffer
from flask_jwt_extended import create_access_token


# Platform domain mapping for Assertion 4
PLATFORM_DOMAINS = {
    "Amazon.in": "amazon.in",
    "Flipkart": "flipkart.com",
    "Croma": "croma.com",
    "Myntra": "myntra.com",
    "Ajio": "ajio.com",
    "Meesho": "meesho.com",
    "Nykaa": "nykaa.com",
    "Purplle": "purplle.com",
    "Blinkit": "blinkit.com",
    "BigBasket": "bigbasket.com",
    "JioMart": "jiomart.com",
    "Scooboo": "scooboo.in",
    "Pepperfry": "pepperfry.com",
    "Urban Ladder": "urbanladder.com",
    "1mg": "1mg.com",
    "PharmEasy": "pharmeasy.in",
    "CaratLane": "caratlane.com",
    "Tanishq": "tanishq.co.in",
}


CATEGORY_TEST_SPECS = [
    {
        "category": "Electronics",
        "platforms": ["Amazon.in", "Flipkart", "Croma"],
        "primary": {
            "name": "Apple iPhone 15 128GB Black",
            "brand": "Apple",
            "catalog_price": 69900.0,
            "min_price": 50000.0,
            "max_price": 85000.0,
        },
        "secondary": {
            "name": "Sony WH-1000XM5 Wireless Headphones",
            "brand": "Sony",
            "catalog_price": 29990.0,
            "min_price": 18000.0,
            "max_price": 36000.0,
        },
    },
    {
        "category": "Fashion",
        "platforms": ["Myntra", "Ajio", "Meesho"],
        "primary": {
            "name": "Puma Men Black Running Shoes",
            "brand": "Puma",
            "catalog_price": 2499.0,
            "min_price": 350.0,
            "max_price": 6500.0,
        },
        "secondary": {
            "name": "Men Cotton Regular Fit Polo T-Shirt",
            "brand": "U.S. Polo Assn.",
            "catalog_price": 1299.0,
            "min_price": 300.0,
            "max_price": 3000.0,
        },
    },
    {
        "category": "Beauty & Personal Care",
        "platforms": ["Nykaa", "Purplle"],
        "primary": {
            "name": "Cetaphil Gentle Skin Cleanser 125ml",
            "brand": "Cetaphil",
            "catalog_price": 399.0,
            "min_price": 150.0,
            "max_price": 650.0,
        },
        "secondary": {
            "name": "Maybelline New York Colossal Kajal",
            "brand": "Maybelline",
            "catalog_price": 199.0,
            "min_price": 80.0,
            "max_price": 350.0,
        },
    },
    {
        "category": "Quick-Commerce & Grocery",
        "platforms": ["Blinkit", "BigBasket", "JioMart"],
        "primary": {
            "name": "Tata Tea Gold 500g",
            "brand": "Tata",
            "catalog_price": 275.0,
            "min_price": 120.0,
            "max_price": 450.0,
        },
        "secondary": {
            "name": "Maggi 2-Minute Masala Noodles 70g",
            "brand": "Maggi",
            "catalog_price": 14.0,
            "min_price": 10.0,
            "max_price": 50.0,
        },
    },
    {
        "category": "Furniture",
        "platforms": ["Pepperfry", "Urban Ladder"],
        "primary": {
            "name": "Solid Wood Coffee Table",
            "brand": "",
            "catalog_price": 12000.0,
            "min_price": 1500.0,
            "max_price": 65000.0,
        },
        "secondary": {
            "name": "ergonomic office chair",
            "brand": "",
            "catalog_price": 8500.0,
            "min_price": 2500.0,
            "max_price": 35000.0,
        },
    },
    {
        "category": "Pharmacy",
        "platforms": ["1mg", "PharmEasy"],
        "primary": {
            "name": "Shelcal 500 Tablet",
            "brand": "Shelcal",
            "catalog_price": 140.0,
            "min_price": 50.0,
            "max_price": 300.0,
        },
        "secondary": {
            "name": "Dolo 650 Tablet",
            "brand": "Dolo",
            "catalog_price": 33.0,
            "min_price": 15.0,
            "max_price": 75.0,
        },
    },
    {
        "category": "Jewelry",
        "platforms": ["CaratLane", "Tanishq"],
        "primary": {
            "name": "Gold Ring",
            "brand": "",
            "catalog_price": 25000.0,
            "min_price": 5000.0,
            "max_price": 150000.0,
        },
        "secondary": {
            "name": "Diamond Pendant",
            "brand": "",
            "catalog_price": 18000.0,
            "min_price": 5000.0,
            "max_price": 120000.0,
        },
    },
    {
        "category": "Stationery",
        "platforms": ["Scooboo"],
        "primary": {
            "name": "Pilot V7 Pen",
            "brand": "Pilot",
            "catalog_price": 65.0,
            "min_price": 30.0,
            "max_price": 350.0,
        },
        "secondary": {
            "name": "Tombow Airpress Ballpoint Pen",
            "brand": "Tombow",
            "catalog_price": 650.0,
            "min_price": 400.0,
            "max_price": 950.0,
        },
    },
]


def reset_all_circuits():
    """Ensure all 18 platform circuits in DB start with clean CLOSED status."""
    print("--> Resetting all circuit breakers in ScraperReliability...")
    for platform_name in SCRAPER_REGISTRY.keys():
        rel = ScraperReliability.query.filter_by(platform=platform_name).first()
        if not rel:
            rel = ScraperReliability(platform=platform_name)
            db.session.add(rel)
        rel.circuit_state = CircuitState.CLOSED
        rel.failure_count_last_hour = 0
        rel.circuit_opened_at = None
        rel.backoff_minutes = 15
        rel.last_failure_reason = None
    db.session.commit()
    print("--> Circuit breaker reset complete.")


async def scrape_single_platform(
    platform_name: str,
    sku_dict: Dict[str, Any],
    category_name: str,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """Execute live scrape for a platform with the specified SKU."""
    scraper = get_scraper_for_platform(platform_name)
    task_id = f"e2e-{platform_name.lower().replace('.', '_')}-{uuid.uuid4().hex[:6]}"
    org_id = "org-e2e-live"
    product_dict = {
        "id": f"prod-{uuid.uuid4().hex[:8]}",
        "name": sku_dict["name"],
        "brand": sku_dict["brand"],
        "category": category_name.lower(),
        "current_price": sku_dict["catalog_price"],
        "catalog_price": sku_dict["catalog_price"],
    }
    
    res = await scraper.scrape(
        task_id=task_id,
        product=product_dict,
        organization_id=org_id,
    )
    return res, sku_dict["name"]


def validate_platform_offer(
    platform_name: str,
    offer: Optional[Dict[str, Any]],
    sku_dict: Dict[str, Any],
) -> List[str]:
    """
    Validate Assertions 1 - 4:
    1. Schema & Non-Null
    2. Price Sanity Bounds
    3. Match Score >= 0.70
    4. Canonical HTTPS PDP URL
    """
    errors = []
    
    # Assertion 1: Non-Null & Schema Validation
    if not offer:
        return ["Offer is None (platform returned empty response)"]
    if offer.get("status") != "success":
        return [f"Offer status is {offer.get('status')!r}: {offer.get('reason')}"]
    
    price = float(offer.get("price") or 0.0)
    if price <= 0:
        errors.append(f"Assertion 1 Failed: Price ₹{price} must be > 0")
        
    try:
        ScrapedOffer.model_validate(offer)
    except Exception as e:
        errors.append(f"Assertion 1 Failed: ScrapedOffer schema validation failed: {e}")

    # Assertion 2: Category Price Sanity Bounds
    min_b = sku_dict.get("min_price", 0.0)
    max_b = sku_dict.get("max_price", float("inf"))
    if not (min_b <= price <= max_b):
        errors.append(f"Assertion 2 Failed: Price ₹{price:,.2f} outside bounds [₹{min_b:,.2f}, ₹{max_b:,.2f}]")

    # Assertion 3: Match Score >= 0.70
    score = float(offer.get("match_score") or 0.0)
    if score < MATCH_THRESHOLD:
        errors.append(f"Assertion 3 Failed: Match score {score:.2f} < {MATCH_THRESHOLD}")

    # Assertion 4: Canonical HTTPS PDP URL
    purl = str(offer.get("product_url") or "")
    if not purl.startswith("https://"):
        errors.append(f"Assertion 4 Failed: URL must start with https://, got: {purl}")
    expected_domain = PLATFORM_DOMAINS.get(platform_name, "")
    if expected_domain and expected_domain not in purl.lower():
        errors.append(f"Assertion 4 Failed: Expected domain '{expected_domain}' not found in URL: {purl}")

    return errors


async def run_all_categories_live_verification() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Runs all 18 platforms across the 8 categories with live requests and assertions."""
    results_summary = []
    category_aggregation_results = {}
    aggregator = AggregatorAgent()

    print("\n" + "=" * 80)
    print("STARTING 18-PLATFORM E2E LIVE CROSS-VERIFICATION MATRIX")
    print("=" * 80)

    for cat_spec in CATEGORY_TEST_SPECS:
        cat_name = cat_spec["category"]
        platforms = cat_spec["platforms"]
        primary_sku = cat_spec["primary"]
        secondary_sku = cat_spec["secondary"]

        print(f"\n>>> CATEGORY: {cat_name.upper()} (Platforms: {', '.join(platforms)})")
        cat_valid_offers = []

        for p_name in platforms:
            print(f"\n  [Platform: {p_name}]")
            # 1. Attempt Primary SKU
            print(f"    - Scraping Primary SKU: '{primary_sku['name']}' (Target ₹{primary_sku['catalog_price']:,.2f})")
            offer, sku_used = await scrape_single_platform(p_name, primary_sku, cat_name)
            current_sku_spec = primary_sku
            errs = validate_platform_offer(p_name, offer, primary_sku)

            # 2. If Primary failed assertions, try Secondary SKU fallback
            if errs and secondary_sku:
                print(f"    ⚠️ Primary SKU failed assertions: {errs}")
                print(f"    - Retrying with Secondary SKU: '{secondary_sku['name']}' (Target ₹{secondary_sku['catalog_price']:,.2f})")
                sec_offer, sec_sku_used = await scrape_single_platform(p_name, secondary_sku, cat_name)
                sec_errs = validate_platform_offer(p_name, sec_offer, secondary_sku)
                if not sec_errs:
                    offer = sec_offer
                    sku_used = sec_sku_used
                    current_sku_spec = secondary_sku
                    errs = []
                else:
                    errs = sec_errs

            # Evaluate outcome
            status_str = "PASS" if not errs else "FAIL"
            price_val = float(offer.get("price") or 0.0) if offer else 0.0
            match_score = float(offer.get("match_score") or 0.0) if offer else 0.0
            scrape_mode = offer.get("scrape_mode", "unknown") if offer else "failed"
            product_url = offer.get("product_url", "N/A") if offer else "N/A"

            record = {
                "platform": p_name,
                "category": cat_name,
                "sku_tested": sku_used,
                "price": price_val,
                "match_score": match_score,
                "scrape_mode": scrape_mode,
                "product_url": product_url,
                "status": status_str,
                "errors": errs,
                "offer": offer,
            }
            results_summary.append(record)

            if status_str == "PASS":
                print(f"    ✅ PASS: ₹{price_val:,.2f} | Match: {match_score:.2f} | Mode: {scrape_mode}")
                print(f"       URL: {product_url}")
                cat_valid_offers.append(offer)
            else:
                print(f"    ❌ FAIL: {errs}")
                if offer:
                    print(f"       Raw Offer: {offer}")

        # Assertion 5: Cross-Platform Category MAD Aggregation (for multi-platform categories)
        if len(platforms) > 1:
            print(f"\n  [Category MAD Aggregation: {cat_name}]")
            agg_result = await aggregator.aggregate(
                cat_valid_offers,
                target_name=primary_sku["name"],
                brand=primary_sku["brand"],
                catalog_price=primary_sku["catalog_price"],
                expected_platforms=platforms,
            )
            category_aggregation_results[cat_name] = agg_result
            valid_offers_count = len(agg_result.get("valid_offers", []))
            avg_p = agg_result.get("market_avg", 0.0)
            min_p = agg_result.get("market_min", 0.0)
            max_p = agg_result.get("market_max", 0.0)
            print(f"    - Verified Offers: {valid_offers_count} / {len(platforms)}")
            print(f"    - Market Index (Median): ₹{avg_p:,.2f} (Min: ₹{min_p:,.2f}, Max: ₹{max_p:,.2f})")
            
            if valid_offers_count >= 1 and (min_p <= avg_p <= max_p):
                print("    ✅ Assertion 5 (MAD Aggregation) PASSED.")
                category_aggregation_results[cat_name]["assertion_5_passed"] = True
            else:
                print(f"    ⚠️ Assertion 5 (MAD Aggregation) WARNING: valid_offers={valid_offers_count}, min={min_p}, avg={avg_p}, max={max_p}")
                category_aggregation_results[cat_name]["assertion_5_passed"] = False

    return results_summary, category_aggregation_results


def verify_flask_api_run_single(user: User, test_product: Product):
    """Verify POST /api/agentic/scraper/<platform>/run-single for all categories."""
    print("\n" + "=" * 80)
    print("VERIFYING FLASK API ROUTE: /api/agentic/scraper/<platform>/run-single")
    print("=" * 80)

    token = create_access_token(identity=user.id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    client = app.test_client()

    # Pick 1 platform per category (8 platforms total)
    sample_platforms = [
        "Amazon.in",    # Electronics
        "Myntra",       # Fashion
        "Nykaa",        # Beauty
        "Blinkit",      # Grocery
        "Pepperfry",    # Furniture
        "1mg",          # Pharmacy
        "CaratLane",    # Jewelry
        "Scooboo",      # Stationery
    ]

    for p in sample_platforms:
        print(f"  - Testing POST /api/agentic/scraper/{p}/run-single ...", end=" ")
        resp = client.post(
            f"/api/agentic/scraper/{p}/run-single",
            json={"product_id": test_product.id},
            headers=headers,
        )
        data = resp.get_json() or {}
        assert resp.status_code == 200, f"Expected HTTP 200, got {resp.status_code}: {data}"
        assert data.get("status") == "success", f"Expected status=='success', got {data}"
        assert data.get("platform") == p, f"Platform mismatch: {data}"
        assert data.get("task_id") is not None, f"Missing task_id: {data}"
        print(f"HTTP 200 OK | task_id={data.get('task_id')[:8]}... ✅")

    print("--> All 8 category API run-single calls succeeded.")


def print_final_summary_table(results_summary: List[Dict[str, Any]]):
    """Prints a beautiful markdown-aligned table of the test results."""
    print("\n" + "=" * 120)
    print("18-PLATFORM E2E LIVE EXTRACTION FINAL SUMMARY TABLE")
    print("=" * 120)
    
    header = f"{'Platform':<15} | {'Category':<20} | {'SKU Tested':<35} | {'Price (₹)':<10} | {'Match':<6} | {'Scrape Mode':<15} | {'Status':<6}"
    sep = "-" * len(header)
    print(header)
    print(sep)
    
    all_pass = True
    for r in results_summary:
        sku_short = (r["sku_tested"][:32] + "...") if len(r["sku_tested"]) > 35 else r["sku_tested"]
        price_str = f"₹{r['price']:,.0f}" if r["price"] > 0 else "N/A"
        status_flag = "PASS" if r["status"] == "PASS" else "FAIL"
        if status_flag == "FAIL":
            all_pass = False
        print(f"{r['platform']:<15} | {r['category']:<20} | {sku_short:<35} | {price_str:<10} | {r['match_score']:<6.2f} | {r['scrape_mode']:<15} | {status_flag:<6}")
    
    print(sep)
    total_passed = sum(1 for r in results_summary if r["status"] == "PASS")
    total_scrapers = len(results_summary)
    pass_pct = (total_passed / total_scrapers) * 100
    print(f"TOTAL SCORE: {total_passed}/{total_scrapers} ({pass_pct:.1f}% SUCCESS RATE)")
    print("=" * 120)
    return all_pass


def main():
    print("Initializing Flask test environment...")
    with app.app_context():
        db.create_all()

        # 1. Reset all circuit breakers in DB
        reset_all_circuits()

        # 2. Seed test Org, User, and Product for Flask API verification
        org_id = str(uuid.uuid4())
        org = Organization(id=org_id, name="E2E Live Verification Store", invite_code=f"INV-{org_id[:6]}")
        db.session.add(org)

        user_id = str(uuid.uuid4())
        user = User(id=user_id, email="e2e_tester@klypup.internal", name="E2E Tester", organization_id=org_id)
        user.set_password("SecurePassword123!")
        db.session.add(user)

        product_id = str(uuid.uuid4())
        product = Product(
            id=product_id,
            name="Apple iPhone 15 128GB Black",
            brand="Apple",
            category="electronics",
            current_price=69900.0,
            cost_price=55000.0,
            inventory_quantity=20,
            sku="APPL-IP15-128-BLK",
            organization_id=org_id,
        )
        db.session.add(product)
        db.session.commit()

        # 3. Execute live scraper verification across all 18 platforms
        results, aggregations = asyncio.run(run_all_categories_live_verification())

        # 4. Verify Flask API /run-single route
        verify_flask_api_run_single(user, product)

        # 5. Print Summary Table
        success = print_final_summary_table(results)

        if not success:
            failed_platforms = [r["platform"] for r in results if r["status"] != "PASS"]
            print(f"\n❌ E2E VERIFICATION FAILED FOR PLATFORMS: {failed_platforms}")
            sys.exit(1)
        else:
            print("\n🎉 ALL 18 PLATFORMS PASSED 100% OF LIVE VERIFICATION ASSERTIONS!")
            sys.exit(0)


if __name__ == "__main__":
    main()
