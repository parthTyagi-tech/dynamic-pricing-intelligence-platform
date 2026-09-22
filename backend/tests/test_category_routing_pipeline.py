import os
import sys
import time
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("FLASK_ENV", "testing")

from app.extensions import db
from app.models.organization import Organization
from app.models.product import Product
from app.models.recommendation import (
    PricingRecommendation,
    RecommendationStatus,
    ApprovalAction,
    ApprovalActionType,
)
from app.models.price_history import PriceHistory
from app.models.recommendation_job import RecommendationJob, RecommendationJobStatus
from app.models.user import User, UserRole
from app.services.recommendation_job_service import (
    create_recommendation_job,
    execute_auto_approval,
)
from app.services import task_worker
from run import app


@pytest.fixture
def test_setup():
    with app.app_context():
        uid = time.time_ns()
        org = Organization(name=f"Org-{uid}", invite_code=f"INV-{uid}")
        db.session.add(org)
        db.session.flush()

        admin = User(name=f"Admin-{uid}", email=f"admin-{uid}@example.com", role=UserRole.ADMIN, organization_id=org.id)
        admin.set_password("SecurePass123!")
        db.session.add(admin)
        db.session.flush()

        product = Product(
            name=f"Pharmacy Product {uid}",
            sku=f"SKU-{uid}",
            category="general",
            category_hint="pharmacy",
            current_price=1000.0,
            cost_price=600.0,
            inventory_quantity=50,
            organization_id=org.id,
        )
        db.session.add(product)
        db.session.commit()

        yield {"org": org, "admin": admin, "product": product}

        # Cleanup
        try:
            PriceHistory.query.filter_by(organization_id=org.id).delete()
            ApprovalAction.query.filter(
                ApprovalAction.recommendation_id.in_(
                    db.session.query(PricingRecommendation.id).filter_by(organization_id=org.id)
                )
            ).delete(synchronize_session=False)
            RecommendationJob.query.filter_by(organization_id=org.id).delete()
            PricingRecommendation.query.filter_by(organization_id=org.id).delete()
            Product.query.filter_by(organization_id=org.id).delete()
            User.query.filter_by(organization_id=org.id).delete()
            Organization.query.filter_by(id=org.id).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()


def test_category_hint_pharmacy_routes_through_task_worker(test_setup, monkeypatch):
    """
    Test 1: category_hint='pharmacy' routes to ['1mg', 'PharmEasy'] through the real
    task_worker entry point, proving target_platforms is None by default and lets
    execute() run category_hint routing.
    """
    with app.app_context():
        product = test_setup["product"]
        org = test_setup["org"]

        rec, job = create_recommendation_job(product, org.id)
        assert job.requested_platforms is None, "Job requested_platforms must be None by default"

        dispatched_targets = []
        from app.services.agentic.supervisor_agent import SupervisorAgent
        original_execute = SupervisorAgent.execute

        async def spy_execute(self, task_id, product_id, organization_id, force_refresh=True, target_platforms=None, simulate_failure_platform=None):
            dispatched_targets.append(target_platforms)
            return await original_execute(
                self, task_id, product_id, organization_id,
                force_refresh=force_refresh, target_platforms=target_platforms,
                simulate_failure_platform=simulate_failure_platform
            )

        monkeypatch.setattr("app.services.agentic.supervisor_agent.SupervisorAgent.execute", spy_execute)

        task_worker.process_pricing_recommendation_task(rec.id, product.id)

        # Confirm target_platforms was passed as None from task_worker
        assert len(dispatched_targets) == 1
        assert dispatched_targets[0] is None

        # Verify task manager dispatched platforms in supervisor mapped to pharmacy platforms
        from app.services.task_state.task_manager import get_task_manager
        task_mgr = get_task_manager()
        matching_tasks = [t for t in task_mgr.tasks.values() if t.product_id == product.id]
        assert len(matching_tasks) > 0
        latest_task = matching_tasks[-1]
        assert "1mg" in latest_task.dispatched_platforms
        assert "PharmEasy" in latest_task.dispatched_platforms


def test_sec10_sanity_bound_blocks_auto_execute_across_both_call_sites(test_setup, monkeypatch):
    """
    Test 2: A >=50% delta recommendation at 0.99 confidence is blocked from APPROVED
    status and forced to human_review / PENDING.
    """
    with app.app_context():
        product = test_setup["product"]
        org = test_setup["org"]

        # 1. Test via PricingStrategyAgent.generate()
        async def mock_compliance(prod, price, rules):
            return {"compliant": True, "final_recommended_price": 400.0, "compliance_notes": "ok"}

        async def mock_pricing(*args, **kwargs):
            return {
                "recommended_price": 400.0,
                "confidence_score": 0.99,
                "rationale": "Extreme price reduction.",
                "strategy": "aggressive_discount",
            }

        monkeypatch.setattr("app.services.ai_pricing_service.compliance_agent.run", mock_compliance)
        monkeypatch.setattr("app.services.ai_pricing_service.pricing_strategy_agent.run", mock_pricing)

        from app.services.ai_pricing_service import PricingStrategyAgent
        res = PricingStrategyAgent.generate(
            product,
            market_data={"avg_competitor_price": 400.0},
            demand_data={"demand_score": 80},
            inventory_data={"inventory_status": "healthy"}
        )

        assert res["sanity_bound_flagged"] is True
        assert res["execution_route"] == "human_review", "SEC-10 must downgrade out-of-bounds to human_review"
        assert "SEC-10 SANITY BOUND FLAGGED" in res["rationale"]

        # 2. Test via shared execute_auto_approval()
        rec, job = create_recommendation_job(product, org.id)
        rec.recommended_price = 400.0  # 60% drop from 1000.0
        rec.confidence_score = 0.99

        executed = execute_auto_approval(rec, product, res)
        assert executed is False
        assert rec.status == RecommendationStatus.PENDING
        assert rec.sanity_bound_flagged is True
        assert product.current_price == 1000.0, "Catalog price must not change on blocked auto-execute"


def test_auto_execute_creates_price_history_and_notification(test_setup, monkeypatch):
    """
    Test 3: PriceHistory is created on auto-execute and notification builds
    a valid competitor-price list without raising AttributeError.
    """
    with app.app_context():
        product = test_setup["product"]
        org = test_setup["org"]

        rec, job = create_recommendation_job(product, org.id)
        rec.recommended_price = 950.0  # 5% change, safe
        rec.confidence_score = 0.95
        rec.platform_prices_snapshot = {
            "Amazon.in": {"price": 940.0, "in_stock": True},
            "Flipkart": {"price": 960.0, "in_stock": True},
        }

        sent_emails = []
        sent_whatsapp = []

        monkeypatch.setattr(
            "app.services.email_service.send_recommendation_action_email",
            lambda **kwargs: sent_emails.append(kwargs)
        )
        monkeypatch.setattr(
            "app.services.whatsapp_service.send_whatsapp_recommendation_action",
            lambda **kwargs: sent_whatsapp.append(kwargs)
        )

        ai_result = {"execution_route": "auto_execute"}
        executed = execute_auto_approval(rec, product, ai_result)

        assert executed is True
        assert product.current_price == 950.0
        assert rec.status == RecommendationStatus.APPROVED

        # Verify PriceHistory record exists in DB
        ph = PriceHistory.query.filter_by(recommendation_id=rec.id).first()
        assert ph is not None
        assert ph.old_price == 1000.0
        assert ph.new_price == 950.0
        assert ph.product_id == product.id
        assert ph.organization_id == org.id

        # Verify ApprovalAction record exists in DB
        action = ApprovalAction.query.filter_by(recommendation_id=rec.id).first()
        assert action is not None
        assert action.action_type == ApprovalActionType.AUTO_EXECUTE
        assert action.previous_price == 1000.0
        assert action.executed_price == 950.0

        # Verify notification was called without AttributeError
        assert len(sent_emails) == 1
        comp_prices = sent_emails[0]["competitor_prices"]
        assert len(comp_prices) == 2
        assert comp_prices[0]["competitor_name"] == "Amazon.in"
        assert comp_prices[0]["competitor_price"] == 940.0


def test_execute_auto_approval_idempotency_and_state_consistency(test_setup, monkeypatch):
    """
    Test 4: Call execute_auto_approval directly from simulated task_worker and
    recommendation_routes contexts to assert identical resulting state.
    """
    with app.app_context():
        product = test_setup["product"]
        org = test_setup["org"]

        # Run 1: Simulated worker call
        rec1, _ = create_recommendation_job(product, org.id)
        rec1.recommended_price = 920.0
        rec1.confidence_score = 0.95
        rec1.platform_prices_snapshot = {"Amazon.in": {"price": 915.0, "stock_status": "in_stock"}}

        monkeypatch.setattr("app.services.email_service.send_recommendation_action_email", lambda **kwargs: None)
        monkeypatch.setattr("app.services.whatsapp_service.send_whatsapp_recommendation_action", lambda **kwargs: None)

        res1 = execute_auto_approval(rec1, product, {"execution_route": "auto_execute"})
        assert res1 is True
        assert product.current_price == 920.0
        assert rec1.status == RecommendationStatus.APPROVED

        ph1 = PriceHistory.query.filter_by(recommendation_id=rec1.id).first()
        assert ph1.old_price == 1000.0
        assert ph1.new_price == 920.0

        # Reset price for Run 2: Simulated routes call
        product.current_price = 1000.0
        db.session.commit()

        rec2, _ = create_recommendation_job(product, org.id)
        rec2.recommended_price = 920.0
        rec2.confidence_score = 0.95
        rec2.platform_prices_snapshot = {"Amazon.in": {"price": 915.0, "stock_status": "in_stock"}}

        res2 = execute_auto_approval(rec2, product, {"execution_route": "auto_execute"})
        assert res2 is True
        assert product.current_price == 920.0
        assert rec2.status == RecommendationStatus.APPROVED

        ph2 = PriceHistory.query.filter_by(recommendation_id=rec2.id).first()
        assert ph2.old_price == 1000.0
        assert ph2.new_price == 920.0
