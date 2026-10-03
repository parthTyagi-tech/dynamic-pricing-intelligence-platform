import uuid
import pytest
from app.extensions import db
from app.models.organization import Organization
from app.models.product import Product
from app.models.recommendation import PricingRecommendation, RecommendationStatus
from app.models.recommendation_job import RecommendationJob, RecommendationJobStatus
from run import app


@pytest.fixture
def test_setup():
    with app.app_context():
        org_id = str(uuid.uuid4())
        org = Organization(id=org_id, name="Test Org", invite_code=f"INV-{org_id[:6]}")
        db.session.add(org)

        prod_id = str(uuid.uuid4())
        product = Product(
            id=prod_id,
            sku=f"SKU-{prod_id[:6]}",
            name="Test Phone",
            brand="Acme",
            category="electronics",
            current_price=1000.0,
            cost_price=600.0,
            inventory_quantity=20,
            organization_id=org_id
        )
        db.session.add(product)

        rec_id = str(uuid.uuid4())
        rec = PricingRecommendation(
            id=rec_id,
            product_id=prod_id,
            organization_id=org_id,
            recommended_price=950.0,
            confidence_score=0.9,
            status="processing"
        )
        db.session.add(rec)

        job_id = str(uuid.uuid4())
        job = RecommendationJob(
            id=job_id,
            recommendation_id=rec_id,
            product_id=prod_id,
            organization_id=org_id,
            status=RecommendationJobStatus.QUEUED
        )
        db.session.add(job)
        db.session.commit()

        yield {
            "org_id": org_id,
            "product_id": prod_id,
            "recommendation_id": rec_id,
            "job_id": job_id
        }


def test_process_task_no_name_error(test_setup, monkeypatch):
    client = app.test_client()

    async def fake_supervisor_execute(*args, **kwargs):
        return {
            "recommendation": {
                "platform_prices_snapshot": {
                    "Amazon": {
                        "price": 950.0,
                        "currency": "INR",
                        "stock_status": "in_stock",
                        "product_title": "Test Phone",
                        "match_score": 0.95,
                        "data_source": "live_scrape"
                    }
                }
            }
        }

    def fake_pricing_generate(product, *args, **kwargs):
        return {
            "recommended_price": 940.0,
            "confidence_score": 0.92,
            "rationale": "Competitive match with solid margin.",
            "ai_summary": "Recommended price is 940.",
            "projected_volume_increase_pct": 5.0,
            "projected_monthly_profit_lift": 200.0,
            "execution_route": "manual",
            "agent_analysis": {
                "market_agent": {"avg_competitor_price": 950.0, "lowest_competitor_price": 950.0},
                "demand_agent": {"demand_score": 75, "seasonal_factor": 1.0},
                "inventory_agent": {"inventory_score": 60, "stock_status": "healthy"}
            }
        }

    monkeypatch.setattr("app.services.agentic.supervisor_agent.SupervisorAgent.execute", fake_supervisor_execute)
    monkeypatch.setattr("app.services.ai_pricing_service.PricingStrategyAgent.generate", fake_pricing_generate)
    monkeypatch.setattr("app.routes.recommendation_routes.PricingStrategyAgent.generate", fake_pricing_generate)
    monkeypatch.setenv("MOCK_SCRAPING", "true")

    res = client.post("/api/recommendations/process-task", json={
        "recommendation_id": test_setup["recommendation_id"],
        "product_id": test_setup["product_id"],
        "job_id": test_setup["job_id"],
        "force_refresh": False
    })

    assert res.status_code == 200, res.get_json()
    data = res.get_json()
    assert data["success"] is True
    assert "Task processed successfully" in data["message"]
