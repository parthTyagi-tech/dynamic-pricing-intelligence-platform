import csv
import io
import json
import time
from pathlib import Path

import requests

BASE = "http://localhost:5000/api"
email = f"http-e2e-{time.time_ns()}@example.com"
password = "StrongPassword123!"
session = requests.Session()
report = {"base": BASE, "checks": []}

def check(name, response, expected):
    ok = response.status_code == expected
    report["checks"].append({"name": name, "status": response.status_code, "expected": expected, "ok": ok})
    if not ok:
        raise RuntimeError(f"{name}: expected {expected}, got {response.status_code}: {response.text[:500]}")
    return response

registration = check("register", session.post(f"{BASE}/auth/register", json={"name": "HTTP E2E Admin", "email": email, "password": password, "organization_name": "HTTP E2E Workspace"}), 201)
token = registration.json().get("token") or registration.json().get("access_token")
if not token:
    login = check("login", session.post(f"{BASE}/auth/login", json={"email": email, "password": password}), 200)
    token = login.json().get("token") or login.json().get("access_token")
session.headers.update({"Authorization": f"Bearer {token}"})

csv_body = io.StringIO()
writer = csv.writer(csv_body)
writer.writerow(["name", "sku", "category", "description", "brand", "barcode", "current_price", "cost_price", "inventory_quantity"])
writer.writerow(["HTTP Integration Product", f"HTTP-{time.time_ns()}", "electronics", "HTTP pipeline product", "Acme", "0000000000000", "1000", "600", "25"])
check("catalog import", session.post(f"{BASE}/products/import-csv", files={"file": ("catalog_sample.csv", csv_body.getvalue(), "text/csv")}), 200)
products = check("products", session.get(f"{BASE}/products"), 200).json()
items = products.get("products", products) if isinstance(products, dict) else products
product_id = items[-1]["id"]

for endpoint in ["dashboard/metrics", "dashboard/revenue", "dashboard/pricing-trends", "dashboard/demand", "dashboard/ai-performance", "dashboard/recommendations", "dashboard/live-activity", "dashboard/live-sales", "dashboard/competitors", "dashboard/scraper-status", "observability/stats", "auth/profile"]:
    check(endpoint, session.get(f"{BASE}/{endpoint}"), 200)
check("connect integration", session.post(f"{BASE}/auth/connect-integration", json={"platform": "shopify", "domain": "http-e2e.example.com"}), 200)
check("integration state", session.get(f"{BASE}/startup/integrations"), 200)
scan = check("alert scan", session.post(f"{BASE}/alerts/scan", json={"product_id": product_id, "previous_prices": {"Amazon": 1000}, "observations": {"Amazon": 900}, "threshold_pct": 5, "min_drop_inr": 10}), 200)
if scan.json().get("alerts"):
    alert_id = scan.json()["alerts"][0]["id"]
    check("alert acknowledgement", session.patch(f"{BASE}/alerts/{alert_id}/acknowledge"), 200)
check("root health", session.get("http://localhost:5000/../health"), 200)

Path("/tmp/klypup_local_http_e2e.json").write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
