import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("MOCK_SCRAPING", "true")

from run import app
from app.extensions import db
from app.models.organization import Organization
from app.models.user import User
from app.models.product import Product
from app.models.recommendation import PricingRecommendation, RecommendationStatus
from app.models.recommendation_job import RecommendationJob, RecommendationJobStatus
from app.services.recommendation_job_service import create_recommendation_job
from app.services.task_worker import _process_pricing_job
from flask_jwt_extended import create_access_token


@pytest.fixture
def product_setup():
    with app.app_context():
        org_id = str(uuid.uuid4())
        org = Organization(id=org_id, name="Deduplication Org", invite_code=f"INV-{org_id[:6]}")
        db.session.add(org)

        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            name="Test User",
            email=f"user-{user_id[:6]}@example.com",
            password_hash="test-hash",
            role="admin",
            organization_id=org_id
        )
        db.session.add(user)

        prod_id = str(uuid.uuid4())
        product = Product(
            id=prod_id,
            sku=f"SKU-{prod_id[:6]}",
            name="Wireless Noise-Cancelling Headphones",
            brand="Sony",
            category="electronics",
            current_price=24990.0,
            cost_price=18000.0,
            inventory_quantity=15,
            organization_id=org_id
        )
        db.session.add(product)
        db.session.commit()

        token = create_access_token(identity=user_id)

        yield {
            "org_id": org_id,
            "user_id": user_id,
            "product_id": prod_id,
            "token": token
        }


def test_single_recommendation_and_job_invariant(product_setup, monkeypatch):
    """
    Processing a recommendation task through the worker must NEVER spawn
    duplicate PricingRecommendation or RecommendationJob rows.
    Exactly 1 recommendation and 1 job must exist.
    """
    with app.app_context():
        product = Product.query.get(product_setup["product_id"])
        org_id = product_setup["org_id"]

        rec, job = create_recommendation_job(product, org_id)

        assert PricingRecommendation.query.filter_by(product_id=product.id).count() == 1
        assert RecommendationJob.query.filter_by(product_id=product.id).count() == 1

        # Mock supervisor execute to simulate completed scraping
        async def fake_supervisor_execute(*args, **kwargs):
            return {
                "status": "succeeded",
                "recommendation": {
                    "platform_prices_snapshot": {
                        "Amazon": {
                            "price": 23990.0,
                            "stock_status": "in_stock",
                            "match_score": 0.95,
                            "product_title": "Sony WH-1000XM5",
                            "data_source": "live_scrape"
                        }
                    }
                }
            }

        def fake_pricing_generate(p, *args, **kwargs):
            return {
                "recommended_price": 23490.0,
                "confidence_score": 0.90,
                "rationale": "Competitive match with solid margin.",
                "ai_summary": "Recommended price is 23490.",
                "projected_volume_increase_pct": 5.0,
                "projected_monthly_profit_lift": 500.0,
                "execution_route": "human_review",
                "agent_analysis": {
                    "market_agent": {"avg_competitor_price": 23990.0},
                    "demand_agent": {"demand_score": 80, "seasonal_factor": 1.0},
                    "inventory_agent": {"inventory_score": 70}
                }
            }

        monkeypatch.setattr("app.services.agentic.supervisor_agent.SupervisorAgent.execute", fake_supervisor_execute)
        monkeypatch.setattr("app.services.ai_pricing_service.PricingStrategyAgent.generate", fake_pricing_generate)

        # Execute processing through task_worker
        _process_pricing_job(rec.id, product.id)

        # Assert invariant: exactly 1 recommendation and 1 job
        recs = PricingRecommendation.query.filter_by(product_id=product.id).all()
        jobs = RecommendationJob.query.filter_by(product_id=product.id).all()

        assert len(recs) == 1, f"Expected 1 PricingRecommendation, found {len(recs)}"
        assert len(jobs) == 1, f"Expected 1 RecommendationJob, found {len(jobs)}"
        assert recs[0].status == RecommendationStatus.PENDING
        assert recs[0].recommended_price == 23490.0
        assert jobs[0].status == RecommendationJobStatus.SUCCEEDED


def test_supersede_older_pending_when_new_recommendation_created(product_setup):
    """
    When a new recommendation job is created for a product that already
    has an active PENDING recommendation, the older one is marked SUPERSEDED.
    """
    with app.app_context():
        product = Product.query.get(product_setup["product_id"])
        org_id = product_setup["org_id"]

        # Rec 1 created and pending
        rec1, job1 = create_recommendation_job(product, org_id)
        rec1.status = RecommendationStatus.PENDING
        db.session.commit()

        assert rec1.status == RecommendationStatus.PENDING

        # Rec 2 created for same product
        rec2, job2 = create_recommendation_job(product, org_id)

        # Verify Rec 1 transitioned to SUPERSEDED
        rec1_reloaded = PricingRecommendation.query.get(rec1.id)
        assert rec1_reloaded.status == RecommendationStatus.SUPERSEDED
        assert rec2.status == "processing"


def test_get_recommendations_query_deduplicates_legacy_pending(product_setup):
    """
    If multiple PENDING recommendations exist for the same product,
    GET /api/recommendations ensures only the newest remains PENDING and
    older duplicates are transitioned to SUPERSEDED.
    """
    client = app.test_client()
    with app.app_context():
        product = Product.query.get(product_setup["product_id"])
        org_id = product_setup["org_id"]

        # Create two pending recommendations directly with explicit timestamps
        now = datetime.utcnow()
        rec_old = PricingRecommendation(
            id=str(uuid.uuid4()),
            product_id=product.id,
            organization_id=org_id,
            recommended_price=24000.0,
            status=RecommendationStatus.PENDING,
            created_at=now - timedelta(hours=1)
        )
        rec_new = PricingRecommendation(
            id=str(uuid.uuid4()),
            product_id=product.id,
            organization_id=org_id,
            recommended_price=23500.0,
            status=RecommendationStatus.PENDING,
            created_at=now
        )
        db.session.add(rec_old)
        db.session.add(rec_new)
        db.session.commit()

        # Query GET /api/recommendations
        headers = {"Authorization": f"Bearer {product_setup['token']}"}
        resp = client.get("/api/recommendations", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()

        # Count of active pending returned must be 1 for this product
        matching = [r for r in data["recommendations"] if r["product_id"] == product.id]
        assert len(matching) == 1
        assert matching[0]["id"] == rec_new.id

        # Database state check
        rec_old_reloaded = PricingRecommendation.query.get(rec_old.id)
        rec_new_reloaded = PricingRecommendation.query.get(rec_new.id)
        assert rec_old_reloaded.status == RecommendationStatus.SUPERSEDED
        assert rec_new_reloaded.status == RecommendationStatus.PENDING
