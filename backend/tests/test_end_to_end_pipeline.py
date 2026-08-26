import os
import sys
import time
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("FLASK_ENV", "testing")

from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.organization import Organization
from app.models.product import Product
from app.models.recommendation import PricingRecommendation, RecommendationStatus
from app.models.market_data import CompetitorPrice
from app.models.price_alert import PriceAlert
from app.models.user import User, UserRole
from app.services import task_worker
from run import app


def test_authenticated_pricing_pipeline_end_to_end(monkeypatch):
    email = f"e2e-{time.time_ns()}@example.com"
    sku = f"E2E-{time.time_ns()}"
    with app.app_context():
        organization = Organization(name="E2E Organization", invite_code=f"INV-{time.time_ns()}")
        db.session.add(organization)
        db.session.flush()
        user = User(name="E2E Admin", email=email, role=UserRole.ADMIN, organization_id=organization.id)
        user.set_password("StrongPassword123!")
        db.session.add(user)
        db.session.flush()
        token = create_access_token(identity=user.id)
        headers = {"Authorization": f"Bearer {token}"}
        client = app.test_client()

        csv = ("name,sku,category,description,brand,barcode,current_price,cost_price,inventory_quantity\n"
               f"Integration Product,{sku},electronics,Test product,Acme,0000000000000,1000,600,25\n")
        imported = client.post("/api/products/import-csv", headers=headers, data={"file": (BytesIO(csv.encode()), "catalog_sample.csv")}, content_type="multipart/form-data")
        assert imported.status_code == 200, imported.get_json()
        product = Product.query.filter_by(organization_id=organization.id, sku=sku).first()
        assert product is not None

        CompetitorPrice(competitor_name="Amazon", competitor_price=950, product_id=product.id, organization_id=organization.id)
        db.session.commit()

        # Keep the real route/queue/DB workflow while making the external scraper and model deterministic.
        async def fake_scraper(**kwargs):
            return {"Amazon": {"price": 930, "in_stock": True, "url": "https://example.com/p"}}
        monkeypatch.setattr("app.services.realtime_scraper.fetch_multi_platform_prices", fake_scraper)
        monkeypatch.setattr("app.services.ai_pricing_service.PricingStrategyAgent.generate", lambda product: {
            "recommended_price": 975.0,
            "confidence_score": 0.91,
            "rationale": "Persisted competitor observation and inventory signal.",
            "ai_summary": "Live three-tier strategy result.",
            "projected_volume_increase_pct": 2.0,
            "projected_monthly_profit_lift": 100.0,
            "agent_analysis": {
                "market_agent": {"competitor_price": 930.0},
                "demand_agent": {"demand_score": 70.0, "seasonal_factor": 1.0},
                "inventory_agent": {"inventory_score": 60.0},
            },
            "execution_route": "manual",
            "fallback_used": False,
        })

        queued = client.post(f"/api/recommendations/generate/{product.id}", headers=headers)
        assert queued.status_code == 202, queued.get_json()
        recommendation_id = queued.get_json()["recommendation"]["id"]
        task_worker.task_queue.join()
        status = client.get(f"/api/recommendations/status/{recommendation_id}", headers=headers)
        assert status.status_code == 200, status.get_json()
        assert status.get_json()["status"] == RecommendationStatus.PENDING
        assert status.get_json()["fallback_used"] is False

        for endpoint in [
            "/api/dashboard/metrics", "/api/dashboard/revenue", "/api/dashboard/pricing-trends",
            "/api/dashboard/demand", "/api/dashboard/ai-performance", "/api/dashboard/recommendations",
            "/api/dashboard/live-activity", "/api/dashboard/live-sales", "/api/dashboard/competitors",
            "/api/dashboard/scraper-status", "/api/observability/stats", "/api/products",
        ]:
            response = client.get(endpoint, headers=headers)
            assert response.status_code == 200, (endpoint, response.get_json())

        connected = client.post("/api/auth/connect-integration", headers=headers, json={"platform": "shopify", "domain": "store.example.com"})
        assert connected.status_code == 200, connected.get_json()
        assert Product.query.filter_by(organization_id=organization.id).count() == 1
        integrations = client.get("/api/startup/integrations", headers=headers)
        assert integrations.status_code == 200
        assert integrations.get_json()["integrations"]["shopify"]["connected"] is True

        scanned = client.post("/api/alerts/scan", headers=headers, json={"product_id": product.id, "previous_prices": {"Amazon": 1000}, "observations": {"Amazon": 900}, "threshold_pct": 5, "min_drop_inr": 10})
        assert scanned.status_code == 200, scanned.get_json()
        alert_id = scanned.get_json()["alerts"][0]["id"]
        acknowledged = client.patch(f"/api/alerts/{alert_id}/acknowledge", headers=headers)
        assert acknowledged.status_code == 200, acknowledged.get_json()

        monkeypatch.setattr("app.routes.approval_routes._finalize_action_email", lambda *args, **kwargs: None)
        approved = client.post(f"/api/approvals/approve/{recommendation_id}", headers=headers)
        assert approved.status_code == 200, approved.get_json()
        history = client.get("/api/approvals/history", headers=headers)
        assert history.status_code == 200
        assert history.get_json()["count"] >= 1

        db.session.delete(product)
        db.session.delete(user)
        db.session.delete(organization)
        db.session.commit()
