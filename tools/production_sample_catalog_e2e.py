from __future__ import annotations

import csv
import io
import os
import time
import uuid
from pathlib import Path

import requests
from openpyxl import Workbook

API = os.environ.get("KLYPUP_API", "https://dynamic-pricing-intelligence-api.vercel.app/api")
SAMPLE = Path(os.environ.get("KLYPUP_SAMPLE", "catalog_sample.csv"))
PASSWORD = "CatalogSampleE2E98263"


def assert_json(response: requests.Response, status: int, label: str) -> dict:
    if response.status_code != status:
        raise AssertionError(f"{label}: expected {status}, got {response.status_code}: {response.text[:400]}")
    payload = response.json()
    if payload.get("success") is False:
        raise AssertionError(f"{label}: {payload}")
    print(f"PASS {label} ({response.status_code})")
    return payload


def run_format(label: str, filename: str, content: bytes, mime: str, expected_rows: int) -> None:
    session = requests.Session()
    email = f"catalog-sample-{label.lower()}-{uuid.uuid4().hex[:12]}@example.com"
    started = time.monotonic()
    registered = assert_json(
        session.post(
            f"{API}/auth/register",
            json={
                "name": f"Catalog Sample {label} E2E",
                "email": email,
                "password": PASSWORD,
                "organization_name": f"Catalog Sample {label} Workspace",
            },
            timeout=45,
        ),
        201,
        f"{label} registration",
    )
    session.headers.update({"Authorization": f"Bearer {registered['token']}"})
    imported = assert_json(
        session.post(
            f"{API}/products/import-csv",
            files={"file": (filename, content, mime)},
            timeout=60,
        ),
        200,
        f"{label} catalog import",
    )
    if imported.get("imported_count") != expected_rows:
        raise AssertionError(f"{label} imported count mismatch: {imported}")
    completed = assert_json(session.post(f"{API}/auth/complete-onboarding", json={}, timeout=45), 200, f"{label} onboarding completion")
    if not completed.get("user", {}).get("onboarding_completed"):
        raise AssertionError(f"{label} onboarding flag was not persisted: {completed}")
    products = assert_json(session.get(f"{API}/products", timeout=45), 200, f"{label} final catalog query")
    if products.get("count") != expected_rows:
        raise AssertionError(f"{label} final catalog count mismatch: {products}")
    metrics = assert_json(session.get(f"{API}/dashboard/metrics", timeout=45), 200, f"{label} dashboard metrics")
    if metrics.get("liveProducts") != expected_rows:
        raise AssertionError(f"{label} liveProducts mismatch: {metrics}")
    print(f"PASS {label} exact sample workflow ({time.monotonic() - started:.2f}s)")


def main() -> None:
    rows = list(csv.DictReader(io.StringIO(SAMPLE.read_text(encoding="utf-8"))))
    if len(rows) != 6:
        raise AssertionError(f"Expected six sample rows, got {len(rows)}")
    csv_content = SAMPLE.read_bytes()
    run_format("CSV", SAMPLE.name, csv_content, "text/csv", len(rows))

    workbook = Workbook()
    sheet = workbook.active
    headers = list(rows[0].keys())
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(header, "") for header in headers])
    xlsx_content = io.BytesIO()
    workbook.save(xlsx_content)
    run_format(
        "XLSX",
        "catalog_sample.xlsx",
        xlsx_content.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        len(rows),
    )
    print("PASS exact catalog_sample.csv coverage for CSV and XLSX")


if __name__ == "__main__":
    main()
