from __future__ import annotations

import csv
import io
import os
import time
import uuid

import requests
from openpyxl import Workbook

API = os.environ.get("KLYPUP_API", "https://dynamic-pricing-intelligence-api.vercel.app/api")
email = f"onboarding-e2e-{uuid.uuid4().hex[:12]}@example.com"
password = "OnboardingE2E98263"


def check(response: requests.Response, expected: int, label: str) -> dict:
    if response.status_code != expected:
        raise AssertionError(f"{label}: expected {expected}, got {response.status_code}: {response.text[:300]}")
    payload = response.json()
    if payload.get("success") is False:
        raise AssertionError(f"{label}: {payload}")
    print(f"PASS {label} ({response.status_code})")
    return payload


def main() -> None:
    session = requests.Session()
    started = time.monotonic()
    registered = check(session.post(f"{API}/auth/register", json={"name": "Onboarding E2E", "email": email, "password": password, "organization_name": "Onboarding E2E Workspace"}, timeout=30), 201, "registration")
    session.headers.update({"Authorization": f"Bearer {registered['token']}"})
    check(session.get(f"{API}/products", timeout=30), 200, "initial catalog query")

    csv_bytes = io.StringIO()
    writer = csv.DictWriter(csv_bytes, fieldnames=["sku", "name", "current_price", "cost_price", "inventory_quantity", "category"])
    writer.writeheader()
    writer.writerow({"sku": "ONBOARD-CSV-1", "name": "Onboarding CSV Product", "current_price": "1299", "cost_price": "700", "inventory_quantity": "12", "category": "Test"})
    check(session.post(f"{API}/products/import-csv", files={"file": ("catalog.csv", csv_bytes.getvalue().encode("utf-8"), "text/csv")}, timeout=30), 200, "CSV import")

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["sku", "name", "current_price", "cost_price", "inventory_quantity", "category"])
    sheet.append(["ONBOARD-XLSX-1", "Onboarding XLSX Product", 2499, 1400, 8, "Test"])
    workbook_bytes = io.BytesIO()
    workbook.save(workbook_bytes)
    check(session.post(f"{API}/products/import-csv", files={"file": ("catalog.xlsx", workbook_bytes.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}, timeout=30), 200, "XLSX import")

    connected = check(session.post(f"{API}/auth/connect-integration", json={"platform": "shopify", "domain": "onboarding-e2e.example.com"}, timeout=30), 200, "store connection")
    if connected.get("catalog_count") != 2:
        raise AssertionError(f"store connection catalog count mismatch: {connected}")
    completed = check(session.post(f"{API}/auth/complete-onboarding", json={}, timeout=30), 200, "onboarding completion")
    if not completed.get("user", {}).get("onboarding_completed"):
        raise AssertionError(f"onboarding flag not persisted: {completed}")
    products = check(session.get(f"{API}/products", timeout=30), 200, "final catalog query")
    if products.get("count") != 2:
        raise AssertionError(f"final catalog count mismatch: {products}")
    print(f"PASS onboarding workflow ({time.monotonic() - started:.2f}s)")


if __name__ == "__main__":
    main()
