import uuid
import pytest
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models.organization import Organization
from app.models.user import User
from app.models.product import Product
from app.models.recommendation import PricingRecommendation, RecommendationStatus, ApprovalAction, ApprovalActionType
from run import app

@pytest.fixture
def reject_setup():
    with app.app_context():
        org_id = str(uuid.uuid4())
        org = Organization(id=org_id, name="Reject Test Org", invite_code=f"INV-{org_id[:6]}")
        db.session.add(org)

        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            name="Test Admin",
            email=f"user-{user_id[:8]}@example.com",
            organization_id=org_id,
            role="admin",
            password_hash="mockhash"
        )
        db.session.add(user)

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
            status=RecommendationStatus.PENDING
        )
        db.session.add(rec)
        db.session.commit()

        token = create_access_token(identity=user_id)

        yield {
            "token": token,
            "user_id": user_id,
            "org_id": org_id,
            "rec_id": rec_id,
            "prod_id": prod_id
        }

def test_reject_recommendation_saves_reason(reject_setup, monkeypatch):
    client = app.test_client()

    monkeypatch.setattr("app.routes.approval_routes._finalize_action_email", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.routes.approval_routes.send_whatsapp_recommendation_action", lambda *args, **kwargs: None)

    reason_text = "Price is below minimum desired margin for this week."
    res = client.post(
        f"/api/approvals/reject/{reject_setup['rec_id']}",
        json={"rejection_reason": reason_text},
        headers={"Authorization": f"Bearer {reject_setup['token']}"}
    )

    assert res.status_code == 200, res.get_json()
    data = res.get_json()
    assert data["success"] is True

    with app.app_context():
        rec = PricingRecommendation.query.get(reject_setup["rec_id"])
        assert rec.status == RecommendationStatus.REJECTED

        action = ApprovalAction.query.filter_by(
            recommendation_id=reject_setup["rec_id"],
            action_type=ApprovalActionType.REJECT
        ).first()
        assert action is not None
        assert action.rejection_reason == reason_text
        assert action.approved_by == reject_setup["user_id"]
