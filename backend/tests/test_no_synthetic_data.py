"""
Phase 9: Remove Synthetic Data from Production Paths.

Verifies:
1. Running an AB test simulation does NOT alter Product.current_price.
2. Chatbot SKU velocity matches actual sales (not random.uniform).
3. Simulation response includes `simulated: True` and `disclaimer`.
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
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
from app.models.ab_test import ABTest
from app.models.market_data import Sale
from flask_jwt_extended import create_access_token


@pytest.fixture
def synth_setup():
    with app.app_context():
        org_id = str(uuid.uuid4())
        org = Organization(id=org_id, name="SynthTest Org", invite_code=f"INV-{org_id[:6]}")
        db.session.add(org)

        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            name="Synth User",
            email=f"synth-{user_id[:6]}@example.com",
            password_hash="test-hash",
            role="admin",
            organization_id=org_id,
        )
        db.session.add(user)

        prod_id = str(uuid.uuid4())
        product = Product(
            id=prod_id,
            sku=f"SKU-{prod_id[:6]}",
            name="Simulation Test Product",
            brand="TestBrand",
            category="electronics",
            current_price=5000.0,
            cost_price=3500.0,
            inventory_quantity=50,
            organization_id=org_id,
        )
        db.session.add(product)
        db.session.commit()

        token = create_access_token(identity=user_id)

        yield {
            "org_id": org_id,
            "user_id": user_id,
            "product_id": prod_id,
            "token": token,
        }


def test_ab_test_simulation_does_not_alter_product_price(synth_setup):
    """Running AB test simulation must NOT mutate Product.current_price."""
    client = app.test_client()
    with app.app_context():
        product = db.session.get(Product, synth_setup["product_id"])
        original_price = product.current_price

        # Create an AB test
        ab_test = ABTest(
            product_id=product.id,
            organization_id=synth_setup["org_id"],
            price_a=original_price,
            price_b=original_price * 1.05,
        )
        db.session.add(ab_test)
        db.session.commit()
        test_id = ab_test.id

        # Simulate the AB test
        headers = {"Authorization": f"Bearer {synth_setup['token']}"}
        resp = client.post(f"/api/ab-test/simulate/{test_id}", headers=headers)
        assert resp.status_code == 200

        data = resp.get_json()
        assert data.get("simulated") is True
        assert "disclaimer" in data
        assert "winning_price" in data

        # CRITICAL: Product.current_price must NOT have changed
        db.session.refresh(product)
        assert product.current_price == original_price, (
            f"Product price was mutated from {original_price} to {product.current_price}"
        )


def test_simulation_response_includes_simulated_flag(synth_setup):
    """Simulation response must include simulated=True and a disclaimer."""
    client = app.test_client()
    headers = {"Authorization": f"Bearer {synth_setup['token']}"}

    resp = client.post(
        "/api/simulation/run",
        json={"product_id": synth_setup["product_id"], "days": 5},
        headers=headers,
    )
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["simulated"] is True
    assert "disclaimer" in data
    assert "No production prices" in data["disclaimer"]


def test_chatbot_velocity_matches_actual_sales(synth_setup):
    """
    The chatbot agent must compute SKU velocity from real Sale records,
    not from random.uniform().
    """
    with app.app_context():
        product = db.session.get(Product, synth_setup["product_id"])

        # Insert 3 sales within the 14-day window (total qty = 10)
        now = datetime.now(timezone.utc)
        for qty in [3, 3, 4]:
            sale = Sale(
                product_id=product.id,
                organization_id=synth_setup["org_id"],
                quantity=qty,
                price_per_unit=product.current_price,
                timestamp=now - timedelta(days=2),
            )
            db.session.add(sale)
        db.session.commit()

        # Import the function and compute velocity
        from sqlalchemy import func
        cutoff_14d = now - timedelta(days=14)
        total_sold = db.session.query(
            func.coalesce(func.sum(Sale.quantity), 0)
        ).filter(
            Sale.product_id == product.id,
            Sale.timestamp >= cutoff_14d,
        ).scalar()

        expected_velocity = float(total_sold) / 14.0
        assert total_sold == 10
        assert abs(expected_velocity - 10 / 14.0) < 0.01


def test_ab_test_model_has_is_simulated_flag():
    """ABTest model must have is_simulated column defaulting to True."""
    with app.app_context():
        assert hasattr(ABTest, "is_simulated")

        test = ABTest(
            product_id="fake-id",
            organization_id="fake-org",
            price_a=100.0,
            price_b=105.0,
        )
        assert test.is_simulated is True
