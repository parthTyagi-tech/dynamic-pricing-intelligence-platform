from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.user import User
from app.models.product import Product
from app.models.ab_test import ABTest
from datetime import datetime, timezone
import random

ab_test_bp = Blueprint("ab_tests", __name__)

@ab_test_bp.route("/start/<product_id>", methods=["POST"])
@jwt_required()
def start_ab_test(product_id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    product = Product.query.filter_by(id=product_id, organization_id=current_user.organization_id).first()
    if not product:
        return {"success": False, "message": "Product not found"}, 404

    data = request.get_json(silent=True) or {}
    price_a = data.get("price_a", product.current_price)
    price_b = data.get("price_b", round(product.current_price * 1.05, 2)) # 5% increase default

    # Check if active test already exists
    active_test = ABTest.query.filter_by(product_id=product.id, status="active").first()
    if active_test:
        return {"success": False, "message": "An active A/B test is already running for this product"}, 400

    new_test = ABTest(
        product_id=product.id,
        organization_id=current_user.organization_id,
        price_a=price_a,
        price_b=price_b
    )
    db.session.add(new_test)
    db.session.commit()

    return {
        "success": True,
        "message": "A/B Test started successfully",
        "ab_test": new_test.to_dict()
    }, 201

@ab_test_bp.route("/simulate/<test_id>", methods=["POST"])
@jwt_required()
def simulate_ab_test(test_id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

    ab_test = ABTest.query.filter_by(id=test_id, organization_id=current_user.organization_id).first()
    if not ab_test or ab_test.status != "active":
        return {"success": False, "message": "Active test not found"}, 404

    # Fast-forward time simulation: randomly generate sales based on slight price elasticity
    # Usually lower price yields higher volume, but higher price yields higher margin
    
    # Simulate Branch A (lower price typically)
    ab_test.sales_a = random.randint(50, 150)
    ab_test.revenue_a = ab_test.sales_a * ab_test.price_a
    
    # Simulate Branch B
    # Price elasticity simulation factor
    price_diff_pct = (ab_test.price_b - ab_test.price_a) / ab_test.price_a
    expected_sales_b_reduction = price_diff_pct * 1.5 # -1.5 price elasticity
    base_sales_b = ab_test.sales_a * (1 - expected_sales_b_reduction)
    ab_test.sales_b = max(0, int(base_sales_b + random.randint(-15, 15)))
    ab_test.revenue_b = ab_test.sales_b * ab_test.price_b

    # Determine winner based on REVENUE (Profit Proxy for this simulation)
    if ab_test.revenue_a > ab_test.revenue_b:
        ab_test.winner = "A"
        winning_price = ab_test.price_a
    else:
        ab_test.winner = "B"
        winning_price = ab_test.price_b

    # End test and lock in the winning price
    ab_test.status = "completed"
    ab_test.completed_at = datetime.now(timezone.utc)

    product = Product.query.get(ab_test.product_id)
    product.current_price = winning_price

    db.session.commit()

    return {
        "success": True,
        "message": f"A/B Test completed. Branch {ab_test.winner} won!",
        "ab_test": ab_test.to_dict()
    }, 200
