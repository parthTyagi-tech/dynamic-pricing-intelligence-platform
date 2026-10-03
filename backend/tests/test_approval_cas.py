from __future__ import annotations

import uuid
import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.audit_log import AuditLog as AuditLogShim
from app.models.audit_loging import AuditLog, PricingRule
from app.models.price_history import PriceHistory
from app.models.pricing_recommendation import (
    PricingRecommendation as PricingRecommendationShim,
    RecommendationStatus as RecommendationStatusShim,
)
from app.models.product import Product
from app.models.recommendation import PricingRecommendation, RecommendationStatus
from app.models.user import User
from app.models.organization import Organization
from app.services.recommendation_job_service import create_recommendation_job
from run import app


@pytest.fixture
def cas_setup():
    with app.app_context():
        org_id = str(uuid.uuid4())
        org = Organization(id=org_id, name="CAS Org", invite_code=f"INV-{org_id[:6]}")
        db.session.add(org)

        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            name="Admin User",
            email=f"admin-{user_id[:6]}@example.com",
            organization_id=org_id,
            role="admin",
            password_hash="mockhash",
        )
        db.session.add(user)

        rule = PricingRule(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            minimum_margin=0.10,
            auto_execute_threshold=0.90,
        )
        db.session.add(rule)

        prod_id = str(uuid.uuid4())
        product = Product(
            id=prod_id,
            sku=f"CAS-SKU-{prod_id[:6]}",
            name="CAS Test Product",
            category="electronics",
            current_price=1000.0,
            cost_price=800.0,
            inventory_quantity=20,
            min_margin_percentage=10.0,
            organization_id=org_id,
        )
        db.session.add(product)
        db.session.commit()

        token = create_access_token(identity=user_id)

        yield {
            "org_id": org_id,
            "user_id": user_id,
            "product": product,
            "token": token,
        }


def test_models_hygiene_and_shims():
    # 1. SUPERSEDED status exists and is in ALL
    assert RecommendationStatus.SUPERSEDED == "superseded"
    assert "superseded" in RecommendationStatus.ALL
    assert RecommendationStatusShim.SUPERSEDED == "superseded"

    # 2. base_price attribute on PricingRecommendation
    rec = PricingRecommendation(
        recommended_price=1200.0,
        base_price=1000.0,
    )
    assert rec.base_price == 1000.0
    rec_dict = rec.to_dict()
    assert rec_dict["base_price"] == 1000.0

    # 3. AuditLog storefront sync fields
    audit = AuditLog(
        action="price_changed",
        organization_id=str(uuid.uuid4()),
        storefront_sync_status="synced",
    )
    assert audit.storefront_sync_status == "synced"
    audit_dict = audit.to_dict()
    assert audit_dict["storefront_sync_status"] == "synced"

    # 4. Shims export matching classes
    assert PricingRecommendationShim is PricingRecommendation
    assert AuditLogShim is AuditLog


def test_supersede_older_pending_recommendations(cas_setup):
    product = cas_setup["product"]
    org_id = cas_setup["org_id"]

    # Create first recommendation job
    rec1, job1 = create_recommendation_job(product, org_id)
    rec1.status = RecommendationStatus.PENDING
    db.session.commit()

    assert rec1.status == RecommendationStatus.PENDING

    # Create second recommendation job for same product
    rec2, job2 = create_recommendation_job(product, org_id)
    rec2.status = RecommendationStatus.PENDING
    db.session.commit()

    # rec1 must have been transitioned to SUPERSEDED
    rec1_reloaded = PricingRecommendation.query.get(rec1.id)
    assert rec1_reloaded.status == RecommendationStatus.SUPERSEDED
    assert rec2.status == RecommendationStatus.PENDING

    # Exactly one PENDING recommendation remains for this product
    pending_count = PricingRecommendation.query.filter_by(
        product_id=product.id,
        organization_id=org_id,
        status=RecommendationStatus.PENDING
    ).count()
    assert pending_count == 1


def test_concurrent_approval_cas_only_one_succeeds(cas_setup):
    client = app.test_client()
    product = cas_setup["product"]
    org_id = cas_setup["org_id"]
    token = cas_setup["token"]

    rec = PricingRecommendation(
        id=str(uuid.uuid4()),
        product_id=product.id,
        recommended_price=1100.0,
        base_price=1000.0,
        confidence_score=0.95,
        status=RecommendationStatus.PENDING,
        organization_id=org_id,
    )
    db.session.add(rec)
    db.session.commit()

    headers = {"Authorization": f"Bearer {token}"}

    # First approval call
    resp1 = client.post(f"/api/approvals/approve/{rec.id}", headers=headers, json={"reason": "Approved round 1"})
    assert resp1.status_code == 200
    assert resp1.get_json()["success"] is True

    # Immediate second approval call on same recommendation
    resp2 = client.post(f"/api/approvals/approve/{rec.id}", headers=headers, json={"reason": "Approved round 2"})
    assert resp2.status_code == 409
    assert resp2.get_json()["success"] is False
    assert "already decided" in resp2.get_json()["message"]

    # Verify exactly one PriceHistory record created
    history = PriceHistory.query.filter_by(recommendation_id=rec.id).all()
    assert len(history) == 1
    assert history[0].old_price == 1000.0
    assert history[0].new_price == 1100.0

    # Product price was updated to 1100.0
    db.session.refresh(product)
    assert product.current_price == 1100.0
