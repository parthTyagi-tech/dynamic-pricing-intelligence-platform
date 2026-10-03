import uuid
import pytest
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models.organization import Organization
from app.models.user import User
from run import app


@pytest.fixture
def multi_org_setup():
    with app.app_context():
        # Org A
        org_a_id = str(uuid.uuid4())
        org_a = Organization(id=org_a_id, name="Org A", invite_code=f"INV-{org_a_id[:6]}")
        db.session.add(org_a)

        user_a_id = str(uuid.uuid4())
        user_a = User(
            id=user_a_id,
            name="Admin A",
            email=f"admin-a-{user_a_id[:6]}@example.com",
            organization_id=org_a_id,
            role="admin",
            password_hash="mockhash"
        )
        db.session.add(user_a)

        # Org B
        org_b_id = str(uuid.uuid4())
        org_b = Organization(id=org_b_id, name="Org B", invite_code=f"INV-{org_b_id[:6]}")
        db.session.add(org_b)

        user_b_id = str(uuid.uuid4())
        user_b = User(
            id=user_b_id,
            name="Admin B",
            email=f"admin-b-{user_b_id[:6]}@example.com",
            organization_id=org_b_id,
            role="admin",
            password_hash="mockhash"
        )
        db.session.add(user_b)
        db.session.commit()

        token_a = create_access_token(identity=user_a_id)
        token_b = create_access_token(identity=user_b_id)

        yield {
            "token_a": token_a,
            "token_b": token_b,
            "org_a_id": org_a_id,
            "org_b_id": org_b_id,
        }


def test_sku_scoping_multi_tenant(multi_org_setup):
    client = app.test_client()

    sku_name = f"SAME-SKU-{str(uuid.uuid4())[:6]}"

    # Org A creates product with sku_name
    res_a = client.post("/api/products", json={
        "sku": sku_name,
        "name": "Widget Org A",
        "current_price": 100.0,
        "cost_price": 60.0
    }, headers={"Authorization": f"Bearer {multi_org_setup['token_a']}"})
    assert res_a.status_code == 201, res_a.get_json()

    # Org B creates product with SAME sku_name -> MUST SUCCEED (multi-tenant isolation)
    res_b = client.post("/api/products", json={
        "sku": sku_name,
        "name": "Widget Org B",
        "current_price": 120.0,
        "cost_price": 70.0
    }, headers={"Authorization": f"Bearer {multi_org_setup['token_b']}"})
    assert res_b.status_code == 201, res_b.get_json()

    # Org A tries to create duplicate sku_name -> MUST FAIL with 400
    res_a_dup = client.post("/api/products", json={
        "sku": sku_name,
        "name": "Widget Org A Duplicate",
        "current_price": 105.0,
        "cost_price": 62.0
    }, headers={"Authorization": f"Bearer {multi_org_setup['token_a']}"})
    assert res_a_dup.status_code == 400
    assert "SKU already exists" in res_a_dup.get_json()["message"]


def test_create_product_requires_sku_and_cost_price(multi_org_setup):
    client = app.test_client()

    # Missing sku
    res = client.post("/api/products", json={
        "name": "No SKU Widget",
        "current_price": 50.0,
        "cost_price": 30.0
    }, headers={"Authorization": f"Bearer {multi_org_setup['token_a']}"})
    assert res.status_code == 400
    assert "sku is required" in res.get_json()["message"]

    # Missing cost_price
    res2 = client.post("/api/products", json={
        "name": "No Cost Widget",
        "sku": "SKU-NO-COST",
        "current_price": 50.0
    }, headers={"Authorization": f"Bearer {multi_org_setup['token_a']}"})
    assert res2.status_code == 400
    assert "cost_price is required" in res2.get_json()["message"]
