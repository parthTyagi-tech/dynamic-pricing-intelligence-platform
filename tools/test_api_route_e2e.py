import os
import sys
import json
import time
import urllib.request
import urllib.parse

BASE_URL = "http://127.0.0.1:5000"

def make_request(method, path, headers=None, data=None):
    url = f"{BASE_URL}{path}"
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req_data = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=req_data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as err:
        err_body = err.read().decode("utf-8")
        return err.status, json.loads(err_body) if err_body else {}

def main():
    print("=======================================================")
    print("STEP 1: LOGIN AS ADMIN")
    print("=======================================================")
    status, login_res = make_request("POST", "/api/auth/login", data={
        "email": "admin@acme.com",
        "password": "password"
    })
    print(f"Login response status: {status}")
    assert status == 200, f"Login failed: {login_res}"
    token = login_res.get("token") or login_res.get("access_token")
    assert token, f"Token not returned: {login_res}"
    auth_headers = {"Authorization": f"Bearer {token}"}
    print("--> Login successful.")

    print("\n=======================================================")
    print("STEP 2: ENSURE STATIONERY PRODUCT EXISTS IN CATALOG")
    print("=======================================================")
    status, prod_res = make_request("GET", "/api/products", headers=auth_headers)
    assert status == 200, f"Fetch products failed: {prod_res}"
    products = prod_res.get("products") or []
    
    target_product = None
    for p in products:
        if "tombow" in p.get("name", "").lower():
            target_product = p
            break
    
    if not target_product:
        print("Creating Tombow Airpress Ballpoint Pen product...")
        status, create_res = make_request("POST", "/api/products", headers=auth_headers, data={
            "name": "Tombow Airpress Ballpoint Pen",
            "brand": "Tombow",
            "category": "stationery",
            "current_price": 650.0,
            "cost_price": 400.0,
            "inventory_quantity": 40,
            "sku": "SKU-TOM-AIR-99"
        })
        print(f"Create product status: {status}")
        assert status in (200, 201), f"Create failed: {create_res}"
        target_product = create_res.get("product")

    assert target_product, "Failed to get or create target stationery product"
    print(f"Target Product: {target_product['name']} (ID: {target_product['id']}, Category: {target_product.get('category')})")

    print("\n=======================================================")
    print("STEP 3: TRIGGER POST /api/recommendations/generate/<product_id>")
    print("=======================================================")
    status, gen_res = make_request("POST", f"/api/recommendations/generate/{target_product['id']}", headers=auth_headers)
    print(f"Generate response status: {status}")
    assert status in (200, 202), f"Generate failed: {gen_res}"
    job_id = gen_res.get("job_id")
    print(f"Job ID: {job_id}")

    print("\n=======================================================")
    print("STEP 4: WAIT FOR ASYNC LIVE EXTRACTION TO COMPLETE")
    print("=======================================================")
    max_wait = 35
    start = time.time()
    rec_found = None
    while time.time() - start < max_wait:
        time.sleep(2)
        s, rec_res = make_request("GET", "/api/recommendations", headers=auth_headers)
        if s == 200:
            recs = rec_res.get("recommendations") or []
            for r in recs:
                if r.get("product_id") == target_product["id"]:
                    rec_found = r
                    break
        if rec_found and rec_found.get("platform_prices_snapshot"):
            print(f"Recommendation ready in {round(time.time() - start, 1)}s!")
            break

    assert rec_found, "Recommendation timed out or was not found!"
    print(f"Recommended Price: INR {rec_found.get('recommended_price')}")
    print(f"Confidence: {rec_found.get('confidence_score')}")
    snapshot = rec_found.get("platform_prices_snapshot") or {}
    print(f"Platform Snapshot count: {len(snapshot)}")
    assert len(snapshot) > 0, "Snapshot must contain verified platform results"
    for platform, pdata in snapshot.items():
        print(f" - Platform: {platform}")
        print(f"   Price: INR {pdata.get('price')}")
        print(f"   Match Score: {pdata.get('match_score')}")
        print(f"   Product URL: {pdata.get('product_url')}")
        print(f"   Latency: {pdata.get('latency_ms')}ms")
        print(f"   Data Source: {pdata.get('data_source')}")
        assert pdata.get("price") > 0, "Price must be positive"
        assert pdata.get("match_score") != 0.92, "Match score must be dynamically computed, not fixed 0.92"
        assert pdata.get("product_url").startswith("https://"), "Must be fully qualified HTTPS URL"
        assert pdata.get("data_source") == "live_scrape", "Must be live_scrape"

    print("\n=======================================================")
    print("STEP 5: VERIFY DATABASE PERSISTENCE OF MARKETPLACE OFFERS")
    print("=======================================================")
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from run import app
    from app.models.recommendation_job import MarketplaceOffer
    with app.app_context():
        offers = MarketplaceOffer.query.filter_by(product_id=target_product["id"]).all()
        print(f"Total MarketplaceOffer rows in DB: {len(offers)}")
        assert len(offers) > 0, "No MarketplaceOffer rows found in DB"
        for o in offers:
            print(f"Offer ID: {o.id}")
            print(f"  Platform: {o.platform}")
            print(f"  Price: INR {o.current_price}")
            print(f"  URL: {o.product_url}")
            print(f"  Source Type: {o.source_type}")
            print(f"  Specs: {o.specifications}")
            assert o.source_type == "live_scrape", f"Invalid source_type: {o.source_type}"
            assert o.product_url.startswith("https://"), f"Invalid URL: {o.product_url}"
            assert o.specifications is not None, "Specs must not be None"
            assert "latency_ms" in o.specifications, "Latency must be present in specifications"

    print("\n=======================================================")
    print("ALL E2E API ROUTE & DB PERSISTENCE CHECKS PASSED (100% GREEN)")
    print("=======================================================")

if __name__ == "__main__":
    main()
