from __future__ import annotations

import uuid
import pytest

from app.extensions import db
from app.models.audit_loging import AuditLog, PricingRule
from app.models.organization import Organization
from app.models.price_history import PriceHistory
from app.models.product import Product
from app.models.recommendation import PricingRecommendation, RecommendationStatus
from app.models.user import User
from app.services.pricing.price_writer import (
    BelowFloorError,
    PriceGuardrailError,
    SanityBoundError,
    StalePriceError,
    apply_price_change,
)
from run import app


@pytest.fixture
def pricing_context():
    with app.app_context():
        org_id = str(uuid.uuid4())
        org = Organization(id=org_id, name="Pricing Test Org", invite_code=f"INV-{org_id[:6]}")
        db.session.add(org)

        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            name="Pricing Admin",
            email=f"admin-{user_id[:6]}@example.com",
            organization_id=org_id,
            role="admin",
            password_hash="mockhash",
        )
        db.session.add(user)

        # 10% minimum margin rule for org
        rule = PricingRule(
            id=str(uuid.uuid4()),
            organization_id=org_id,
            minimum_margin=0.10,
            auto_execute_threshold=0.90,
        )
        db.session.add(rule)

        # Product with cost 1000, current price 1200, min_margin_percentage 10%
        # Floor = 1000 * (1 + 10/100) = 1100.00
        prod_id = str(uuid.uuid4())
        product = Product(
            id=prod_id,
            sku=f"PRICING-TEST-{prod_id[:6]}",
            name="Pricing Test Product",
            category="electronics",
            current_price=1200.0,
            cost_price=1000.0,
            inventory_quantity=50,
            min_margin_percentage=10.0,
            organization_id=org_id,
        )
        db.session.add(product)
        db.session.commit()

        yield {
            "org_id": org_id,
            "user_id": user_id,
            "product": product,
        }


def test_below_floor_rejection(pricing_context):
    product = pricing_context["product"]
    user_id = pricing_context["user_id"]

    # Floor is 1100.0. Attempting 1050.0 should raise BelowFloorError
    with pytest.raises(BelowFloorError) as exc_info:
        apply_price_change(
            product=product,
            new_price=1050.0,
            actor_user_id=user_id,
            source="test_below_floor",
            sanity_override=True,  # Bypass sanity to isolate floor check
        )

    assert "below computed margin floor" in str(exc_info.value)
    # Price must not be mutated
    assert product.current_price == 1200.0

    # No PriceHistory or AuditLog should be written
    history_count = PriceHistory.query.filter_by(product_id=product.id).count()
    audit_count = AuditLog.query.filter_by(entity_id=product.id).count()
    assert history_count == 0
    assert audit_count == 0


def test_sanity_bound_rejection_and_flagging(pricing_context):
    product = pricing_context["product"]
    user_id = pricing_context["user_id"]

    # Current price is 1200.0. 50% bound is [600.0, 1800.0].
    # Recommending 2000.0 (> +50%) or 500.0 (< -50%)
    rec = PricingRecommendation(
        id=str(uuid.uuid4()),
        product_id=product.id,
        recommended_price=2000.0,
        base_price=1200.0,
        confidence_score=0.9,
        organization_id=product.organization_id,
        status=RecommendationStatus.PENDING,
        sanity_bound_flagged=False,
    )
    db.session.add(rec)
    db.session.commit()

    with pytest.raises(SanityBoundError) as exc_info:
        apply_price_change(
            product=product,
            new_price=2000.0,
            actor_user_id=user_id,
            source="test_sanity_violation",
            recommendation=rec,
            sanity_override=False,
        )

    assert "exceeding the 50% sanity bound" in str(exc_info.value)
    # Sanity bound must be flagged on recommendation
    assert rec.sanity_bound_flagged is True
    # Price must remain untouched
    assert product.current_price == 1200.0


def test_sanity_override_success(pricing_context):
    product = pricing_context["product"]
    user_id = pricing_context["user_id"]

    # With sanity_override=True, an admin can approve 2000.0
    rec = PricingRecommendation(
        id=str(uuid.uuid4()),
        product_id=product.id,
        recommended_price=2000.0,
        base_price=1200.0,
        confidence_score=0.9,
        organization_id=product.organization_id,
        status=RecommendationStatus.PENDING,
        sanity_bound_flagged=True,
    )
    db.session.add(rec)
    db.session.commit()

    res = apply_price_change(
        product=product,
        new_price=2000.0,
        actor_user_id=user_id,
        source="test_admin_override",
        recommendation=rec,
        sanity_override=True,
        reason="Market demand surge justified by admin",
    )

    assert res["old_price"] == 1200.0
    assert res["new_price"] == 2000.0
    assert product.current_price == 2000.0

    # Exactly one PriceHistory and one AuditLog record written
    history = PriceHistory.query.filter_by(product_id=product.id).all()
    assert len(history) == 1
    assert history[0].old_price == 1200.0
    assert history[0].new_price == 2000.0

    audit = AuditLog.query.filter_by(entity_id=product.id, action="price_changed").all()
    assert len(audit) == 1
    assert audit[0].after_value == {"current_price": 2000.0}
    assert audit[0].extra_metadata["sanity_override"] is True


def test_stale_price_optimistic_concurrency(pricing_context):
    product = pricing_context["product"]
    user_id = pricing_context["user_id"]

    # Expected base is 1150, but actual product price is 1200
    with pytest.raises(StalePriceError) as exc_info:
        apply_price_change(
            product=product,
            new_price=1250.0,
            actor_user_id=user_id,
            source="test_stale_concurrency",
            expected_base_price=1150.0,
        )

    assert "Base price has drifted" in str(exc_info.value)
    assert product.current_price == 1200.0


def test_drop_over_50_percent_flags_sanity_bound(pricing_context):
    product = pricing_context["product"]
    user_id = pricing_context["user_id"]

    # Test correction 4: drop > 50% must set sanity_bound_flagged
    # Current: 1200. Drop to 500 is >50% drop (and also below floor 1100).
    rec = PricingRecommendation(
        id=str(uuid.uuid4()),
        product_id=product.id,
        recommended_price=500.0,
        base_price=1200.0,
        organization_id=product.organization_id,
        status=RecommendationStatus.PENDING,
        sanity_bound_flagged=False,
    )
    db.session.add(rec)
    db.session.commit()

    with pytest.raises(PriceGuardrailError):
        apply_price_change(
            product=product,
            new_price=500.0,
            actor_user_id=user_id,
            source="test_drop_evaluation",
            recommendation=rec,
            sanity_override=False,
        )

    # Sanity bound must be flagged even though floor was also violated
    assert rec.sanity_bound_flagged is True
