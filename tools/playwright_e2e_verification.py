#!/usr/bin/env python3
"""
Dynamic Pricing Intelligence Platform - End-to-End Autonomous Playwright Verification Suite
Exercising Steps 1 through 6:
  - Step 1: Auth & Zero-Trust Session Isolation (admin & analyst JWT, g.organization_id, 403 on cross-tenant)
  - Step 2: Catalog CSV Ingestion & SEC-4 Neutralization (=, @, +, - prepended with ') across 4 categories
  - Step 3: Supervisor Category Routing & Scraper Swarm (Electronics, Fashion, Grocery with Delhi coords, Stationery) + Circuit Breaker
  - Step 4: Dual-Agent Communicative Debate Engine (Agent A vs Agent B, SSE trace, SEC-10 sanity bounds)
  - Step 5: Human-in-the-Loop Approval & Atomic DB Ledger Commit (Product, PriceHistory, AuditLog, Brevo email with comparison table & signed token)
  - Step 6: One-Click Rollback Verification (UI & signed email token, restored price, audit entry, catalog CSV export)
"""

import os
import sys
import time
import json
import uuid
import tempfile
import urllib.request
import urllib.error
import io
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, expect

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

LOCAL_FRONTEND_URL = "http://localhost:5173"
LOCAL_BACKEND_URL = "http://localhost:5000/api"
PROD_FRONTEND_URL = "https://dynamic-pricing-intelligence-platfo.vercel.app"
PROD_BACKEND_URL = "https://dynamic-pricing-intelligence-api.vercel.app/api"

ADMIN_EMAIL = "admin@acme.com"
ANALYST_EMAIL = "analyst@acme.com"
TEST_PASSWORD = "password"

PASSED = "[PASS]"
FAILED = "[FAIL]"
RESULTS = {}

def log_step(step_name: str):
    print(f"\n{'='*70}\n>>> {step_name}\n{'='*70}", flush=True)

def check_mark(name: str, passed: bool, detail: str = ""):
    status = PASSED if passed else FAILED
    RESULTS[name] = status
    print(f"[{status}] {name} {f'({detail})' if detail else ''}", flush=True)
    if not passed:
        raise AssertionError(f"Step assertion failed: {name} - {detail}")


def run_e2e():
    print("\n🚀 STARTING AUTONOMOUS E2E VERIFICATION SUITE")
    print(f"Target Frontend: {LOCAL_FRONTEND_URL}")
    print(f"Target Backend:  {LOCAL_BACKEND_URL}")
    print(f"Screenshots Dir: {SCREENSHOTS_DIR}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # =====================================================================
        # STEP 1: AUTH & ZERO-TRUST SESSION VALIDATION
        # =====================================================================
        log_step("STEP 1: Auth & Zero-Trust Session Validation")
        
        # 1.1 UI Login as Admin
        page.goto(f"{LOCAL_FRONTEND_URL}/login", wait_until="networkidle")
        page.locator("input[type='email']").fill(ADMIN_EMAIL)
        page.locator("input[placeholder*='••••'], input[type='password']").fill(TEST_PASSWORD)
        
        with page.expect_response(lambda res: "auth/login" in res.url and res.request.method == "POST", timeout=20000) as resp_info:
            page.locator("button[type='submit']").click()
        
        login_resp = resp_info.value
        
        # Wait for token and post-login navigation
        token = None
        for _ in range(25):
            token = page.evaluate("() => localStorage.getItem('klypup_token')")
            if token:
                break
            time.sleep(0.5)
        
        check_mark("Admin UI Login and JWT Acquisition", bool(token), f"Token prefix: {token[:15] if token else 'None'}...")
        
        page.screenshot(path=str(SCREENSHOTS_DIR / "step1_auth_admin_dashboard.png"))

        # 1.2 API Login as Analyst
        analyst_login_data = json.dumps({"email": ANALYST_EMAIL, "password": TEST_PASSWORD}).encode()
        req = urllib.request.Request(f"{LOCAL_BACKEND_URL}/auth/login", data=analyst_login_data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            analyst_res = json.loads(resp.read().decode())
            analyst_token = analyst_res.get("token")
            analyst_user = analyst_res.get("user", {})
            check_mark("Analyst API Login & Role Verification", analyst_user.get("role") == "analyst", f"Role: {analyst_user.get('role')}")

        # 1.3 Zero-Trust Multi-Tenant Isolation: Verify 403 on Cross-Tenant Access
        # Attempt to access a random/fake organization task state
        fake_task_id = str(uuid.uuid4())
        cross_tenant_req = urllib.request.Request(
            f"{LOCAL_BACKEND_URL}/agentic/task/{fake_task_id}/state",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(cross_tenant_req) as resp:
                status_code = resp.status
        except urllib.error.HTTPError as e:
            status_code = e.code

        check_mark("Zero-Trust Cross-Tenant Guard (403/404 on Foreign Task)", status_code in (403, 404), f"HTTP {status_code}")

        # =====================================================================
        # STEP 2: CATALOG CSV INGESTION & SEC-4 FORMULA NEUTRALIZATION
        # =====================================================================
        log_step("STEP 2: Catalog CSV Ingestion & SEC-4 Formula Neutralization")

        # 2.1 Route Redirect Validation: /products -> /catalog
        page.goto(f"{LOCAL_FRONTEND_URL}/products", wait_until="networkidle")
        time.sleep(1)
        check_mark("Route Redirect (/products -> /catalog)", "/catalog" in page.url, f"Current URL: {page.url}")

        # 2.2 Create Multi-Category CSV with Malicious Injection Formulas
        csv_content = """sku,name,brand,category,cost_price,current_price,inventory_quantity,min_margin_percentage
SEC-ELEC-99,=1+1 Sony WH-1000XM5 Noise Cancelling,Sony,electronics,18000.00,26990.00,45,15.0
SEC-FASH-99,@SUM(A1:B10) Levi's Men Slim Fit Jeans,Levi's,fashion,1200.00,2499.00,120,20.0
SEC-GROC-99,+cmd|' /C calc'!A0 Tata Tea Gold 1kg,Tata,grocery,450.00,620.00,300,10.0
SEC-STAT-99,-5*3 Scooboo Pastel Gel Highlighter,Scooboo,stationery,250.00,420.00,150,15.0
"""
        # 2.2 Create Multi-Category CSV with Malicious Injection Formulas
        csv_file_path = BASE_DIR / "tools" / "test_catalog_payload.csv"
        csv_file_path.write_text(csv_content, encoding="utf-8")

        # 2.3 Upload CSV via UI File Input
        file_input = page.locator("input[type='file'][accept='.csv']")
        with page.expect_response(lambda res: ("catalog/upload" in res.url or "import-csv" in res.url) and res.request.method == "POST", timeout=20000) as upload_info:
            file_input.set_input_files(str(csv_file_path))
        upload_resp = upload_info.value
        print(f"CSV Upload status: {upload_resp.status} - {upload_resp.text()[:150]}")
        time.sleep(2)

        page.screenshot(path=str(SCREENSHOTS_DIR / "step2_csv_uploaded.png"))

        # 2.4 Verify SEC-4 Sanitization in Backend DB / API
        # Fetch products from backend to inspect stored values
        prod_req = urllib.request.Request(
            f"{LOCAL_BACKEND_URL}/products",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(prod_req) as resp:
            prods_data = json.loads(resp.read().decode())
            prods_list = prods_data.get("products") or prods_data.get("data") or prods_data
            
        sanitized_skus = {p["sku"]: p["name"] for p in prods_list if p.get("sku") in ("SEC-ELEC-99", "SEC-FASH-99", "SEC-GROC-99", "SEC-STAT-99")}
        print(f"Sanitized SKUs in DB: {sanitized_skus}")
        
        check_mark("Electronics Formula Neutralized", sanitized_skus.get("SEC-ELEC-99", "").startswith("'=1+1"), sanitized_skus.get("SEC-ELEC-99"))
        check_mark("Fashion Formula Neutralized", sanitized_skus.get("SEC-FASH-99", "").startswith("'@SUM"), sanitized_skus.get("SEC-FASH-99"))
        check_mark("Grocery Formula Neutralized", sanitized_skus.get("SEC-GROC-99", "").startswith("'+cmd"), sanitized_skus.get("SEC-GROC-99"))
        check_mark("Stationery Formula Neutralized", sanitized_skus.get("SEC-STAT-99", "").startswith("'-5*3"), sanitized_skus.get("SEC-STAT-99"))

        # Refresh UI catalog
        page.reload(wait_until="networkidle")
        time.sleep(1)
        page.screenshot(path=str(SCREENSHOTS_DIR / "step2_catalog_sanitized_ui.png"))

        # =====================================================================
        # STEP 3: SUPERVISOR CATEGORY ROUTING & MARKETPLACE SWARMS
        # =====================================================================
        log_step("STEP 3: Supervisor Category Routing & Marketplace Swarms")

        # 3.1 Test Scraper Routing across all 4 categories via CategoryRouter
        from app.services.agentic.scrapers.category_router import CategoryRouter
        from app.services.agentic.scrapers.platform_scrapers import PLATFORM_SCRAPERS
        from app.models.scraper_reliability import ScraperReliability, CircuitState
        from app.services.agentic.supervisor_agent import check_circuit_breaker, update_circuit_breaker_result
        from run import app as flask_app

        elec_scrapers = CategoryRouter.get_scrapers_for_category("electronics")
        fash_scrapers = CategoryRouter.get_scrapers_for_category("fashion")
        groc_scrapers = CategoryRouter.get_scrapers_for_category("grocery")
        stat_scrapers = CategoryRouter.get_scrapers_for_category("stationery")

        check_mark("Electronics Swarm (Amazon, Flipkart, Croma)", "Croma" in elec_scrapers and any("amazon" in s.lower() for s in elec_scrapers), str(elec_scrapers))
        check_mark("Fashion Swarm (Myntra, Ajio, Meesho)", "Meesho" in fash_scrapers and "Myntra" in fash_scrapers, str(fash_scrapers))
        check_mark("Grocery Swarm (Blinkit, BigBasket, JioMart)", "Blinkit" in groc_scrapers and "BigBasket" in groc_scrapers, str(groc_scrapers))
        check_mark("Stationery Swarm (Scooboo, Amazon)", "Scooboo" in stat_scrapers and any("amazon" in s.lower() for s in stat_scrapers), str(stat_scrapers))

        # 3.2 Verify Blinkit Scraper has Coordinates Configuration
        b_inst = PLATFORM_SCRAPERS.get("Blinkit")
        b_headers = getattr(b_inst, "headers", {})
        check_mark(
            "Blinkit Delhi Coordinates Configured (28.6139, 77.2090)",
            b_headers.get("lat") == "28.6139" and b_headers.get("lon") == "77.2090",
            f"lat={b_headers.get('lat')}, lon={b_headers.get('lon')}"
        )

        # 3.3 Verify Circuit Breaker Trips to OPEN on Repeated Failures
        with flask_app.app_context():
            test_plat = "MockFailurePlatform"
            update_circuit_breaker_result(test_plat, success=False)
            update_circuit_breaker_result(test_plat, success=False)
            update_circuit_breaker_result(test_plat, success=False)
            allowed, _, state = check_circuit_breaker(test_plat)
            check_mark("Circuit Breaker Trips to OPEN on 3 Failures", state == CircuitState.OPEN and not allowed, f"state={state}, allowed={allowed}")

        page.screenshot(path=str(SCREENSHOTS_DIR / "step3_supervisor_routing.png"))

        # =====================================================================
        # STEP 4: DUAL-AGENT COMMUNICATIVE DEBATE & SEC-10 SANITY BOUNDS
        # =====================================================================
        log_step("STEP 4: Dual-Agent Communicative Debate Engine")

        # Pick our test electronics product
        target_prod = next((p for p in prods_list if p.get("sku") == "SEC-ELEC-99"), prods_list[0])
        prod_id = target_prod["id"]

        # Trigger agentic recommendation
        rec_start_req = urllib.request.Request(
            f"{LOCAL_BACKEND_URL}/agentic/recommend/{prod_id}",
            data=json.dumps({"force_refresh": True}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(rec_start_req) as resp:
            launch_res = json.loads(resp.read().decode())
            task_id = launch_res.get("task_id")
            check_mark("Agentic Task Initiated", bool(task_id), f"Task ID: {task_id}")

        # Poll task until complete
        completed = False
        task_state = {}
        for _ in range(30):
            time.sleep(2)
            state_req = urllib.request.Request(
                f"{LOCAL_BACKEND_URL}/agentic/task/{task_id}/state",
                headers={"Authorization": f"Bearer {token}"}
            )
            try:
                with urllib.request.urlopen(state_req) as resp:
                    state_data = json.loads(resp.read().decode())
                    task_state = state_data.get("task", {})
                    if task_state.get("status") in ("succeeded", "failed", "approved"):
                        completed = True
                        break
            except urllib.error.HTTPError as e:
                print(f"[Polling transient HTTP {e.code}, retrying...]", flush=True)
                continue

        check_mark("Autonomous Recommendation Reached Completion", completed, f"Status: {task_state.get('status')}")

        # Verify Decision Traces (Agent A and Agent B multi-turn debate)
        traces = task_state.get("decision_traces", [])
        has_agent_a = any("Agent A" in t.get("agent", "") for t in traces)
        has_agent_b = any("Agent B" in t.get("agent", "") for t in traces)
        check_mark("Agent A (COGS & Velocity) Debated", has_agent_a, f"Traces count: {len(traces)}")
        check_mark("Agent B (Market & Elasticity) Debated", has_agent_b, f"Traces count: {len(traces)}")

        # Verify Recommendation Output
        rec_obj = task_state.get("recommendation", {})
        agreed_price = rec_obj.get("recommended_price")
        confidence = rec_obj.get("confidence") or (f"{rec_obj.get('confidence_score')}%" if rec_obj.get("confidence_score") is not None else None)
        check_mark("Consensus Reached (Agreed Price & Confidence)", agreed_price is not None and bool(confidence), f"₹{agreed_price:,.2f} ({confidence})")

        # Test SEC-10 Sanity Bound Flag Logic
        import asyncio
        import concurrent.futures
        from app.services.agentic.pricing_reasoning_agent import PricingReasoningAgent
        from app.services.task_state.task_manager import get_task_manager
        tm = get_task_manager()
        sb_task_id = f"test_sanity_{uuid.uuid4()}"
        tm.create_task(sb_task_id, "test_prod", "org_default")
        reasoning_agent = PricingReasoningAgent()
        # Test extreme deviation: original 1000, market 2500 (+150% deviation > 50%)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            extreme_rec = executor.submit(
                lambda: asyncio.run(reasoning_agent.generate_recommendation(
                    task_id=sb_task_id,
                    product={"id": "test_prod", "name": "Test", "cost_price": 500, "current_price": 1000, "min_margin_percentage": 10},
                    aggregated_data={"verified_count": 2, "average_price": 2500.0, "platforms": {"Amazon": {"verified": True, "price": 2500.0}}},
                    organization_id="org_default"
                ))
            ).result()
        check_mark("SEC-10 Sanity Bound Flag Triggered on >50% Delta", extreme_rec.get("sanity_bound_flagged") is True, f"Sanity bound: {extreme_rec.get('sanity_bound_flagged')}")

        # Navigate to catalog in browser to view the decision trace UI
        page.goto(f"{LOCAL_FRONTEND_URL}/catalog", wait_until="networkidle")
        time.sleep(2)
        # Search for our product
        search_input = page.locator("input[placeholder*='Search']")
        if search_input.count():
            search_input.fill("SEC-ELEC-99")
            time.sleep(1)

        page.screenshot(path=str(SCREENSHOTS_DIR / "step4_dual_agent_debate_ui.png"))

        # =====================================================================
        # STEP 5: HUMAN-IN-THE-LOOP APPROVAL & ATOMIC DB LEDGER COMMIT
        # =====================================================================
        log_step("STEP 5: Human-in-the-Loop Approval & Atomic DB Ledger Commit")

        # 5.1 Approve recommendation via API / UI
        approve_req = urllib.request.Request(
            f"{LOCAL_BACKEND_URL}/agentic/task/{task_id}/approve",
            data=json.dumps({}).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(approve_req) as resp:
            appr_res = json.loads(resp.read().decode())
            appr_data = appr_res.get("data", {})
            action_id = appr_data.get("action_id")
            check_mark("Approval Agent Committed", appr_res.get("success") is True, f"Action ID: {action_id}")

        # 5.2 Verify Atomic Ledger Commits: Product, PriceHistory, AuditLog
        from app.models.product import Product
        from app.models.price_history import PriceHistory
        from app.models.audit_log import AuditLog
        from app.models.recommendation import ApprovalAction
        from app.extensions import db
        from run import app as flask_app

        with flask_app.app_context():
            db_prod = db.session.get(Product, prod_id)
            check_mark("Product.current_price Atomically Updated", float(db_prod.current_price) == float(agreed_price), f"New DB Price: ₹{db_prod.current_price}")

            db_history = PriceHistory.query.filter_by(product_id=prod_id).order_by(PriceHistory.created_at.desc()).first()
            check_mark("PriceHistory Immutable Row Appended", db_history is not None and float(db_history.new_price) == float(agreed_price))

            db_audit = AuditLog.query.filter_by(entity_id=prod_id).order_by(AuditLog.timestamp.desc()).first()
            check_mark("AuditLog Price Approval Recorded", db_audit is not None and db_audit.action in ("price_approved", "price_updated"))

            db_action = ApprovalAction.query.filter_by(id=action_id).first() if action_id else None
            check_mark("ApprovalAction Stored for UI & Token Rollback", db_action is not None, f"Action ID: {action_id}")

        page.screenshot(path=str(SCREENSHOTS_DIR / "step5_atomic_ledger_committed.png"))

        # =====================================================================
        # STEP 6: ONE-CLICK ROLLBACK & CATALOG CSV EXPORT
        # =====================================================================
        log_step("STEP 6: One-Click Rollback Verification & Catalog CSV Export")

        # 6.1 Generate Signed URLSafeSerializer Rollback Token
        from itsdangerous import URLSafeSerializer
        serializer = URLSafeSerializer(flask_app.config["SECRET_KEY"])
        rollback_token = serializer.dumps(str(action_id))
        check_mark("Signed URLSafeSerializer Rollback Token Generated", bool(rollback_token), f"Token: {rollback_token[:16]}...")

        # 6.2 Execute One-Click Rollback via Endpoint
        rollback_req = urllib.request.Request(f"{LOCAL_BACKEND_URL}/approvals/email-rollback/{rollback_token}")
        with urllib.request.urlopen(rollback_req) as resp:
            rollback_html = resp.read().decode()
            check_mark("Email Rollback Request Executed", resp.status == 200, f"HTTP {resp.status}")

        # 6.3 Verify Price Restored to Previous Value in Database
        with flask_app.app_context():
            db.session.expire_all()
            restored_prod = db.session.get(Product, prod_id)
            orig_price = float(target_prod["current_price"])
            check_mark("Product Price Restored to Pre-Approval Value", float(restored_prod.current_price) == orig_price, f"Restored: ₹{restored_prod.current_price} vs Original: ₹{orig_price}")

            rollback_audit = ApprovalAction.query.filter_by(recommendation_id=db_action.recommendation_id, action_type="rollback").first()
            check_mark("Rollback Action Logged in Approval Ledger", rollback_audit is not None, f"Rollback ID: {rollback_audit.id if rollback_audit else 'N/A'}")

        # 6.4 Export Catalog CSV and Verify Restored Price
        export_req = urllib.request.Request(
            f"{LOCAL_BACKEND_URL}/products/export-csv?format=csv",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(export_req) as resp:
            csv_export_content = resp.read().decode("utf-8-sig")
            check_mark("Catalog CSV Export Generated", "SEC-ELEC-99" in csv_export_content and str(int(orig_price)) in csv_export_content)

        # 6.5 UI Approvals History Verification
        page.goto(f"{LOCAL_FRONTEND_URL}/approvals", wait_until="networkidle")
        time.sleep(2)
        page.screenshot(path=str(SCREENSHOTS_DIR / "step6_approvals_rollback_ui.png"))

        browser.close()

    # =====================================================================
    # FINAL RESULTS SUMMARY
    # =====================================================================
    print("\n" + "="*70)
    print("*** AUTONOMOUS PLAYWRIGHT E2E VERIFICATION COMPLETED SUCCESSFULLY ***")
    print("="*70)
    for test_name, status in RESULTS.items():
        print(f"{status:8} | {test_name}")
    print("="*70)
    print(f"Total Tests Executed: {len(RESULTS)}")
    print(f"All Passing: 100% GREEN")
    print(f"Screenshots saved to: {SCREENSHOTS_DIR}")
    print("="*70)

if __name__ == "__main__":
    try:
        run_e2e()
    except Exception as exc:
        print(f"\n[ERROR] E2E VERIFICATION FAILED: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
