from __future__ import annotations

import csv
import io
import os
import time
import uuid
from pathlib import Path

import requests

API = os.environ.get("KLYPUP_API", "https://dynamic-pricing-intelligence-api.vercel.app/api")
SAMPLE = Path(os.environ.get("KLYPUP_SAMPLE", "catalog_sample.csv"))
PASSWORD = "RecommendationE2E98263"


def check(response: requests.Response, expected: int, label: str) -> dict:
    if response.status_code != expected:
        raise AssertionError(f"{label}: expected {expected}, got {response.status_code}: {response.text[:500]}")
    data = response.json()
    if data.get("success") is False:
        raise AssertionError(f"{label}: {data}")
    print(f"PASS {label} ({response.status_code})")
    return data


def main() -> None:
    rows = list(csv.DictReader(io.StringIO(SAMPLE.read_text(encoding="utf-8"))))
    session = requests.Session()
    email = f"recommendation-e2e-{uuid.uuid4().hex[:12]}@example.com"
    registered = check(session.post(f"{API}/auth/register", json={
        "name": "Recommendation E2E",
        "email": email,
        "password": PASSWORD,
        "organization_name": "Recommendation E2E Workspace",
    }, timeout=60), 201, "registration")
    session.headers.update({"Authorization": f"Bearer {registered['token']}"})
    imported = check(session.post(f"{API}/products/import-csv", files={
        "file": (SAMPLE.name, SAMPLE.read_bytes(), "text/csv")
    }, timeout=60), 200, "catalog import")
    if imported.get("imported_count") != len(rows):
        raise AssertionError(f"unexpected import count: {imported}")
    check(session.post(f"{API}/auth/complete-onboarding", json={}, timeout=45), 200, "onboarding completion")
    products = check(session.get(f"{API}/products", timeout=45), 200, "product query")
    product = products["products"][0] if products.get("products") else products["data"][0]
    product_id = product["id"]
    queued = check(session.post(f"{API}/recommendations/generate/{product_id}", json={}, timeout=60), 202, "recommendation queue")
    recommendation = queued["recommendation"]
    recommendation_id = recommendation["id"]
    job_id = queued.get("job", {}).get("id") or queued.get("job_id")
    print(f"INFO queued job {job_id}")

    deadline = time.monotonic() + 180
    seen_agents: set[str] = set()
    final = None
    while time.monotonic() < deadline:
        response = session.get(f"{API}/recommendations/status/{recommendation_id}", timeout=45)
        status = check(response, 200, "recommendation status")
        job = status.get("job") or {}
        for event in job.get("events", []):
            seen_agents.add(event.get("agent", ""))
        state = str(job.get("status") or status.get("status") or "").lower()
        print(f"INFO state={state} progress={job.get('progress_percent')} agent={job.get('current_agent')}")
        if state in {"succeeded", "completed", "approved", "rejected", "failed"}:
            final = status
            break
        time.sleep(5)
    if final is None:
        raise AssertionError("recommendation did not reach a terminal state within 180 seconds")
    job = final.get("job") or {}
    if str(job.get("status", "")).lower() == "failed":
        raise AssertionError(f"recommendation job failed: {job.get('error_message')}")
    if not {"scraper", "market", "inventory", "orchestrator"}.intersection(seen_agents):
        raise AssertionError(f"no durable agent events observed: {seen_agents}")
    details = check(session.get(f"{API}/recommendations/{recommendation_id}/details", timeout=45), 200, "recommendation details")
    offers = details.get("job", {}).get("offers", [])
    print(f"PASS durable recommendation terminal state ({job.get('status')})")
    print(f"PASS agent events observed ({sorted(seen_agents)})")
    print(f"INFO marketplace offers persisted: {len(offers)}")
    print("PASS production recommendation workflow")


if __name__ == "__main__":
    main()
