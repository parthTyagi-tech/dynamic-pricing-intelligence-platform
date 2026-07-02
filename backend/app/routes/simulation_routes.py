import math
import random
from flask import Blueprint, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.user import User
from app.models.product import Product
from app.models.audit_loging import PricingRule

simulation_bp = Blueprint("simulation", __name__)


@simulation_bp.route("/run", methods=["POST"])
@jwt_required()
def run_simulation():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    data = request.get_json() or {}
    product_id = data.get("product_id")
    elasticity = float(data.get("elasticity", 1.5))
    days = int(data.get("days", 30))

    if not product_id:
        return {"success": False, "message": "product_id is required"}, 400

    product = Product.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()

    if not product:
        return {"success": False, "message": "Product not found in organization catalog"}, 404

    # Fetch organizational rules
    rule = PricingRule.query.filter_by(
        organization_id=current_user.organization_id
    ).first()
    min_margin = rule.minimum_margin if rule else 0.15

    # Simulation constants
    cost = product.cost_price
    base_price = product.current_price
    base_qty = product.inventory_quantity

    # Determine base units sold per day based on product category
    category = product.category.lower()
    if "ele" in category:
        base_daily_units = 12.0
    elif "app" in category:
        base_daily_units = 25.0
    else:
        base_daily_units = 18.0

    timeline_points = []
    total_actual_rev = 0.0
    total_ai_rev = 0.0
    total_actual_prof = 0.0
    total_ai_prof = 0.0
    
    # Initialize current price variables
    price_actual = base_price
    price_ai = base_price

    # Seed random to ensure deterministic behavior per request if needed
    random.seed(42)

    for i in range(1, days + 1):
        # 1. Simulate competitor price fluctuations (using sine waves + noise)
        comp_price = base_price * (1.0 + 0.06 * math.sin(i / 4.0) + random.uniform(-0.02, 0.02))
        
        # 2. Simulate demand indicators
        trend_score = 0.5 + 0.28 * math.sin(i / 6.0) + random.uniform(-0.04, 0.04)
        trend_score = max(min(trend_score, 1.0), 0.0)
        
        # Seasonality factor
        seasonal_factor = 1.0 + 0.2 * math.cos(i / 8.0)
        daily_vol_factor = base_daily_units * seasonal_factor

        # 3. Emulate Klypup Agent Rules
        # Market positioning adjustment
        gap_pct = ((price_ai - comp_price) / comp_price * 100) if comp_price > 0 else 0
        market_adj = -gap_pct * 0.35
        
        # Demand adjustments
        demand_adj = (trend_score - 0.5) * 12.0

        # Inventory levels
        inv_adj = 0.0
        if base_qty < 10:
            inv_adj = 4.0
        elif base_qty > 100:
            inv_adj = -6.0

        # Pricing Strategy composite price
        composite_adj = (market_adj * 0.35) + (demand_adj * 0.35) + (inv_adj * 0.30)
        composite_adj = max(min(composite_adj, 15.0), -15.0)

        # Recommended dynamic price
        next_ai_price = round(price_ai * (1.0 + composite_adj / 100.0), 2)

        # Compliance adjustment checks
        margin_at_ai = ((next_ai_price - cost) / next_ai_price) if next_ai_price > 0 else 0.0
        if margin_at_ai < min_margin:
            # Shift price to meet compliance floor
            next_ai_price = round(cost / (1.0 - min_margin), 2)

        # 4. Calculate Sales Volume Quantities (using log-linear Price Elasticity model)
        # Baseline sales volume
        Q_actual = max(int(daily_vol_factor), 1)
        
        # AI dynamic sales volume (impacted by price ratio to the power of negative elasticity)
        price_ratio = next_ai_price / base_price
        Q_ai = max(int(daily_vol_factor * (price_ratio ** -elasticity)), 1)

        # 5. Financial aggregates
        day_actual_rev = price_actual * Q_actual
        day_ai_rev = next_ai_price * Q_ai
        
        day_actual_prof = (price_actual - cost) * Q_actual
        day_ai_prof = (next_ai_price - cost) * Q_ai

        total_actual_rev += day_actual_rev
        total_ai_rev += day_ai_rev
        
        total_actual_prof += day_actual_prof
        total_ai_prof += day_ai_prof

        # Record timeline point
        timeline_points.append({
            "day": i,
            "actual_price": round(price_actual, 2),
            "ai_price": round(next_ai_price, 2),
            "competitor_price": round(comp_price, 2),
            "actual_revenue": round(day_actual_rev, 2),
            "ai_revenue": round(day_ai_rev, 2),
            "actual_profit": round(day_actual_prof, 2),
            "ai_profit": round(day_ai_prof, 2),
            "actual_quantity": Q_actual,
            "ai_quantity": Q_ai
        })

        # Update dynamic pricing pointer for next step simulation
        price_ai = next_ai_price

    # 6. Lift percentages
    rev_lift_pct = round(((total_ai_rev - total_actual_rev) / total_actual_rev * 100), 2) if total_actual_rev > 0 else 0.0
    prof_lift_pct = round(((total_ai_prof - total_actual_prof) / total_actual_prof * 100), 2) if total_actual_prof > 0 else 0.0

    return {
        "success": True,
        "product": {
            "id": product.id,
            "name": product.name,
            "sku": product.sku,
            "current_price": base_price,
            "cost_price": cost
        },
        "summary": {
            "total_actual_revenue": round(total_actual_rev, 2),
            "total_ai_revenue": round(total_ai_rev, 2),
            "total_actual_profit": round(total_actual_prof, 2),
            "total_ai_profit": round(total_ai_prof, 2),
            "revenue_lift_pct": rev_lift_pct,
            "profit_lift_pct": prof_lift_pct,
            "days_simulated": days,
            "elasticity_applied": elasticity
        },
        "timeline": timeline_points
    }, 200
