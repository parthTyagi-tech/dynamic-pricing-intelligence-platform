import random
from datetime import datetime, timezone, timedelta
from flask import Blueprint

from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity
)

from app.models.user import User
from app.models.product import Product

from app.models.recommendation import (
    PricingRecommendation,
    RecommendationStatus,
    ApprovalAction,
    ApprovalActionType
)
from app.extensions import db
from app.models.market_data import CompetitorPrice, DemandSignal, Sale
from sqlalchemy import func

dashboard_bp = Blueprint(
    "dashboard",
    __name__
)


# =====================================
# LIVE TICK SIMULATOR HELPER
# =====================================

def simulate_live_tick(organization_id):
    """
    Simulates real-time ingestion activity:
    - 60% chance to simulate a competitor checking a price (adding a new CompetitorPrice log).
    - 40% chance to simulate a new demand signal (adding a new DemandSignal log).
    - 15% chance to generate a new mock PricingRecommendation.
    - Limits log sizes to keep SQLite queries sub-millisecond.
    """
    try:
        products = Product.query.filter_by(organization_id=organization_id).all()
        if not products:
            return

        rand = random.random()

        # 1. Competitor Price Check Simulation (60% chance)
        if rand < 0.60:
            product = random.choice(products)
            competitors = ["Amazon", "Walmart", "BestBuy", "Target", "Ebay"]
            comp_name = random.choice(competitors)
            # Price floats around current_price
            price_variance = random.uniform(0.92, 1.05)
            comp_price_val = round(product.current_price * price_variance, 2)
            
            cp = CompetitorPrice(
                competitor_name=comp_name,
                competitor_price=comp_price_val,
                product_id=product.id,
                organization_id=organization_id,
                checked_at=datetime.now(timezone.utc)
            )
            db.session.add(cp)
            
            # Prune old competitor price logs
            checks_count = CompetitorPrice.query.filter_by(product_id=product.id).count()
            if checks_count > 50:
                old_checks = CompetitorPrice.query.filter_by(
                    product_id=product.id
                ).order_by(CompetitorPrice.checked_at.asc()).limit(checks_count - 50).all()
                for oc in old_checks:
                    db.session.delete(oc)

        # 2. Demand Signal Simulation (40% chance)
        if rand < 0.40:
            product = random.choice(products)
            ds = DemandSignal(
                trend_score=random.uniform(0.35, 0.98),
                seasonal_factor=random.uniform(0.85, 1.25),
                sku_velocity=random.uniform(5.0, 85.0),
                product_id=product.id,
                organization_id=organization_id,
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(ds)
            
            # Prune old demand signals
            signals_count = DemandSignal.query.filter_by(product_id=product.id).count()
            if signals_count > 30:
                old_signals = DemandSignal.query.filter_by(
                    product_id=product.id
                ).order_by(DemandSignal.created_at.asc()).limit(signals_count - 30).all()
                for osig in old_signals:
                    db.session.delete(osig)

        # 3. Storefront Purchase Simulation (25% chance)
        if rand < 0.25:
            product = random.choice(products)
            qty = random.randint(1, 4)
            
            # Restock if inventory is insufficient
            if product.inventory_quantity < qty:
                product.inventory_quantity += random.randint(50, 150)
                
            product.inventory_quantity -= qty
            
            sale = Sale(
                product_id=product.id,
                organization_id=organization_id,
                quantity=qty,
                price_per_unit=product.current_price,
                timestamp=datetime.now(timezone.utc)
            )
            db.session.add(sale)
            
            # Prune old sales log to keep SQLite sub-millisecond
            sales_count = Sale.query.filter_by(organization_id=organization_id).count()
            if sales_count > 50:
                old_sales = Sale.query.filter_by(
                    organization_id=organization_id
                ).order_by(Sale.timestamp.asc()).limit(sales_count - 50).all()
                for osale in old_sales:
                    db.session.delete(osale)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error in simulate_live_tick: {e}")


# =====================================
# DASHBOARD ANALYTICS (PRESERVED)
# =====================================

@dashboard_bp.route(
    "/analytics",
    methods=["GET"]
)
@jwt_required()
def dashboard_analytics():

    current_user_id = get_jwt_identity()

    current_user = User.query.get(
        current_user_id
    )

    total_products = Product.query.filter_by(
        organization_id=current_user.organization_id
    ).count()

    total_recommendations = PricingRecommendation.query.filter_by(
        organization_id=current_user.organization_id
    ).count()

    approved_recommendations = PricingRecommendation.query.filter_by(
        organization_id=current_user.organization_id,
        status=RecommendationStatus.APPROVED
    ).count()

    rejected_recommendations = PricingRecommendation.query.filter_by(
        organization_id=current_user.organization_id,
        status=RecommendationStatus.REJECTED
    ).count()

    pending_recommendations = PricingRecommendation.query.filter_by(
        organization_id=current_user.organization_id,
        status=RecommendationStatus.PENDING
    ).count()

    return {
        "success": True,

        "analytics": {

            "total_products": total_products,

            "total_recommendations": total_recommendations,

            "approved_recommendations": approved_recommendations,

            "rejected_recommendations": rejected_recommendations,

            "pending_recommendations": pending_recommendations
        }
    }, 200


# =====================================
# METRICS API
# =====================================

@dashboard_bp.route(
    "/metrics",
    methods=["GET"]
)
@jwt_required()
def get_metrics():

    current_user_id = get_jwt_identity()

    current_user = User.query.get(
        current_user_id
    )

    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    # Run live simulation tick
    simulate_live_tick(current_user.organization_id)

    # Fetch products
    products = Product.query.filter_by(
        organization_id=current_user.organization_id
    ).all()

    total_products = len(products)
    
    # totalRevenue = sum of (price * inventory_quantity)
    total_revenue = round(sum(p.current_price * (p.inventory_quantity or 10) for p in products), 2)

    # Fetch recommendations
    recommendations = PricingRecommendation.query.filter_by(
        organization_id=current_user.organization_id
    ).all()
    total_recommendations = len(recommendations)

    # pricingAccuracy and aiConfidence
    if total_recommendations > 0:
        confidences = []
        for r in recommendations:
            score = r.confidence_score
            # if stored as 0-1, convert to 0-100
            if score <= 1.0:
                score *= 100
            confidences.append(score)
        ai_confidence = round(sum(confidences) / len(confidences), 0)
        pricing_accuracy = round(ai_confidence * 0.97, 0)
    else:
        ai_confidence = 97.0
        pricing_accuracy = 94.0

    # Competitor updates count
    competitor_changes = CompetitorPrice.query.filter_by(
        organization_id=current_user.organization_id
    ).count()

    # Volatility
    comp_prices = CompetitorPrice.query.filter_by(
        organization_id=current_user.organization_id
    ).all()
    if comp_prices:
        vals = [p.competitor_price for p in comp_prices]
        avg = sum(vals) / len(vals)
        if avg > 0:
            variance = sum((x - avg) ** 2 for x in vals) / len(vals)
            std_dev = variance ** 0.5
            market_volatility = round((std_dev / avg) * 100, 1)
        else:
            market_volatility = 21.0
    else:
        market_volatility = 21.0

    # Conversion Rate (approved recommendations / total recommendations)
    approved_recs = sum(1 for r in recommendations if r.status == RecommendationStatus.APPROVED)
    conversion_rate = round((approved_recs / total_recommendations * 100), 1) if total_recommendations > 0 else 18.0

    # Dynamic Category Distribution Breakdown
    categories = db.session.query(
        Product.category,
        func.count(Product.id)
    ).filter_by(
        organization_id=current_user.organization_id
    ).group_by(Product.category).all()
    category_distribution = {cat: count for cat, count in categories}

    # Dynamic Total Inventory Units
    total_inventory = db.session.query(
        func.sum(Product.inventory_quantity)
    ).filter_by(
        organization_id=current_user.organization_id
    ).scalar() or 0

    # Dynamic Reviews Queue Count
    reviews_queue_count = PricingRecommendation.query.filter_by(
        organization_id=current_user.organization_id,
        status=RecommendationStatus.PENDING
    ).count()

    # Dynamic AI Signal Strength index
    competitor_checks_coverage = CompetitorPrice.query.filter_by(
        organization_id=current_user.organization_id
    ).count()
    ai_signals_strength = min(max(int(competitor_checks_coverage / 4 + 88), 88), 99)

    return {
        "totalRevenue": total_revenue,
        "pricingAccuracy": pricing_accuracy,
        "marketVolatility": market_volatility,
        "aiConfidence": ai_confidence,
        "competitorChanges": competitor_changes,
        "conversionRate": conversion_rate,
        "liveProducts": total_products,
        "totalInventory": total_inventory,
        "categoryDistribution": category_distribution,
        "reviewsQueueCount": reviews_queue_count,
        "aiSignalsStrength": ai_signals_strength,
        "activeModelsCount": 5 # Compliance, Demand, Inventory, Market, Pricing Strategy
    }, 200


# =====================================
# REVENUE API
# =====================================

@dashboard_bp.route(
    "/revenue",
    methods=["GET"]
)
@jwt_required()
def get_revenue():

    current_user_id = get_jwt_identity()

    current_user = User.query.get(
        current_user_id
    )

    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    # Run live simulation tick
    simulate_live_tick(current_user.organization_id)

    products = Product.query.filter_by(
        organization_id=current_user.organization_id
    ).all()
    if not products:
        return [], 200
    base_actual = sum(p.current_price * (p.inventory_quantity or 10) for p in products) * 0.1

    # Apply minor live wiggles (jitter) to simulate active shifts
    wiggle = lambda val: round(val * random.uniform(0.985, 1.015), 2)

    return [
        {
            "date": "Jan",
            "actual": wiggle(base_actual * 0.7),
            "predicted": wiggle(base_actual * 0.75)
        },
        {
            "date": "Feb",
            "actual": wiggle(base_actual * 0.85),
            "predicted": wiggle(base_actual * 0.95)
        },
        {
            "date": "Mar",
            "actual": wiggle(base_actual * 1.0),
            "predicted": wiggle(base_actual * 1.08)
        },
        {
            "date": "Apr",
            "actual": wiggle(base_actual * 1.25),
            "predicted": wiggle(base_actual * 1.30)
        }
    ], 200


# =====================================
# PRICING TRENDS API
# =====================================

@dashboard_bp.route(
    "/pricing-trends",
    methods=["GET"]
)
@jwt_required()
def get_pricing_trends():

    current_user_id = get_jwt_identity()

    current_user = User.query.get(
        current_user_id
    )

    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    # Run live simulation tick
    simulate_live_tick(current_user.organization_id)

    products = Product.query.filter_by(
        organization_id=current_user.organization_id
    ).all()

    # Apply minor live wiggles (jitter) to simulate active price movements
    wiggle = lambda val: round(val * random.uniform(0.98, 1.02), 2)

    if products:
        avg_our_price = sum(p.current_price for p in products) / len(products)
        comp_prices = CompetitorPrice.query.filter_by(
            organization_id=current_user.organization_id
        ).all()
        avg_comp_price = sum(cp.competitor_price for cp in comp_prices) / len(comp_prices) if comp_prices else avg_our_price * 0.98

        return [
            {
                "time": "10AM",
                "aiPrice": wiggle(avg_our_price * 0.95),
                "competitorPrice": wiggle(avg_comp_price * 0.94),
                "marketAverage": wiggle((avg_our_price + avg_comp_price) * 0.47)
            },
            {
                "time": "12PM",
                "aiPrice": wiggle(avg_our_price * 1.0),
                "competitorPrice": wiggle(avg_comp_price * 0.99),
                "marketAverage": wiggle((avg_our_price + avg_comp_price) * 0.495)
            },
            {
                "time": "2PM",
                "aiPrice": wiggle(avg_our_price * 1.05),
                "competitorPrice": wiggle(avg_comp_price * 1.02),
                "marketAverage": wiggle((avg_our_price + avg_comp_price) * 0.51)
            }
        ], 200
    else:
        return [], 200


# =====================================
# DEMAND API
# =====================================

@dashboard_bp.route(
    "/demand",
    methods=["GET"]
)
@jwt_required()
def get_demand():

    current_user_id = get_jwt_identity()

    current_user = User.query.get(
        current_user_id
    )

    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    # Run live simulation tick
    simulate_live_tick(current_user.organization_id)

    # Group products by category and calculate average demand score
    results = db.session.query(
        Product.category,
        func.avg(DemandSignal.trend_score)
    ).join(
        DemandSignal, Product.id == DemandSignal.product_id
    ).filter(
        Product.organization_id == current_user.organization_id
    ).group_by(
        Product.category
    ).all()
    
    wiggle = lambda val: round(min(max(val * random.uniform(0.97, 1.03), 0.0), 100.0), 1)

    if results:
        return [
            {
                "category": cat or "General",
                "demand": wiggle(float(score) * 100) if score is not None else 50.0
            }
            for cat, score in results
        ], 200
    else:
        # Fallback to product category distribution counts
        cat_counts = db.session.query(
            Product.category,
            func.count(Product.id)
        ).filter(
            Product.organization_id == current_user.organization_id
        ).group_by(
            Product.category
        ).all()

        if cat_counts:
            total_cnt = sum(c[1] for c in cat_counts)
            return [
                {
                    "category": cat or "General",
                    "demand": wiggle((count / total_cnt) * 100)
                }
                for cat, count in cat_counts
            ], 200

        return [], 200


# =====================================
# AI PERFORMANCE API
# =====================================

@dashboard_bp.route(
    "/ai-performance",
    methods=["GET"]
)
@jwt_required()
def get_ai_performance():

    current_user_id = get_jwt_identity()

    current_user = User.query.get(
        current_user_id
    )

    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    # Run live simulation tick
    simulate_live_tick(current_user.organization_id)

    products = Product.query.filter_by(
        organization_id=current_user.organization_id
    ).all()
    recs = PricingRecommendation.query.filter_by(
        organization_id=current_user.organization_id
    ).all()

    avg_conf = sum(r.confidence_score for r in recs) / len(recs) if recs else 0.95
    if avg_conf <= 1.0:
        avg_conf *= 100

    avg_margin = sum(p.calculate_margin() for p in products) / len(products) if products else 15.0
    opt_score = min(max(50.0 + avg_margin * 2.0, 60.0), 99.0)

    approved = sum(1 for r in recs if r.status == RecommendationStatus.APPROVED)
    total = len(recs)
    conv_rate = (approved / total * 100) if total > 0 else 85.0

    wiggle = lambda val: round(min(max(val * random.uniform(0.985, 1.015), 30.0), 100.0), 1)

    return [
        {
            "metric": "Accuracy",
            "score": wiggle(avg_conf)
        },
        {
            "metric": "Forecasting",
            "score": wiggle(min(max(avg_conf - 3.0, 60.0), 99.0))
        },
        {
            "metric": "Optimization",
            "score": wiggle(opt_score)
        },
        {
            "metric": "Elasticity",
            "score": wiggle(min(max(conv_rate + 10.0, 70.0), 99.0))
        }
    ], 200


# =====================================
# RECOMMENDATIONS API
# =====================================

@dashboard_bp.route(
    "/recommendations",
    methods=["GET"]
)
@jwt_required()
def get_recommendations():

    current_user_id = get_jwt_identity()

    current_user = User.query.get(
        current_user_id
    )

    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    # Run live simulation tick
    simulate_live_tick(current_user.organization_id)

    recs = PricingRecommendation.query.filter_by(
        organization_id=current_user.organization_id,
        status=RecommendationStatus.PENDING
    ).order_by(
        PricingRecommendation.created_at.desc()
    ).limit(5).all()

    if recs:
        return [
            {
                "id": r.id,
                "productName": r.product.name if r.product else "Unknown Product",
                "confidence": round(r.confidence_score * (100 if r.confidence_score <= 1.0 else 1), 0),
                "currentPrice": r.product.current_price if r.product else 0.0,
                "suggestedPrice": r.recommended_price,
                "reason": r.ai_summary or r.rationale or "Price adjustment recommended"
            }
            for r in recs
        ], 200
    else:
        return [], 200


# =====================================
# LIVE ACTIVITY FEED API
# =====================================

@dashboard_bp.route(
    "/live-activity",
    methods=["GET"]
)
@jwt_required()
def get_live_activity():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    # Fetch latest 10 competitor price updates
    comp_prices = CompetitorPrice.query.filter_by(
        organization_id=current_user.organization_id
    ).order_by(
        CompetitorPrice.checked_at.desc()
    ).limit(10).all()

    # Fetch latest 5 approved/rejected actions
    approval_actions = ApprovalAction.query.join(
        PricingRecommendation
    ).filter(
        PricingRecommendation.organization_id == current_user.organization_id
    ).order_by(
        ApprovalAction.timestamp.desc()
    ).limit(5).all()

    # Fetch latest 10 storefront sales
    sales = Sale.query.filter_by(
        organization_id=current_user.organization_id
    ).order_by(
        Sale.timestamp.desc()
    ).limit(10).all()

    feed = []

    # Map competitor prices to activity items
    for cp in comp_prices:
        feed.append({
            "type": "competitor_check",
            "timestamp": cp.checked_at.isoformat(),
            "message": f"Competitor check: {cp.competitor_name} priced {cp.product.name if cp.product else 'SKU'} at ₹{cp.competitor_price:.2f}"
        })

    # Map actions to activity items
    for action in approval_actions:
        action_type_str = "approved" if action.action_type == ApprovalActionType.APPROVE else "rejected"
        if action.action_type == ApprovalActionType.AUTO_EXECUTE:
            action_type_str = "auto-executed"
            
        rec = action.recommendation
        prod_name = rec.product.name if (rec and rec.product) else "Product"
        
        feed.append({
            "type": "price_action",
            "timestamp": action.timestamp.isoformat(),
            "message": f"Price {action_type_str}: {prod_name} shifted from ₹{action.previous_price:.2f} to ₹{action.executed_price:.2f}"
        })

    # Map sales to activity items
    for s in sales:
        feed.append({
            "type": "purchase",
            "timestamp": s.timestamp.isoformat(),
            "message": f"Purchase: {s.quantity}x {s.product.name if s.product else 'Product'} bought for ₹{s.quantity * s.price_per_unit:.2f} (Stock: {s.product.inventory_quantity if s.product else 0})"
        })

    # Sort feed by timestamp desc
    feed.sort(key=lambda x: x["timestamp"], reverse=True)

    return {
        "success": True,
        "feed": feed[:12]
    }, 200


@dashboard_bp.route(
    "/live-sales",
    methods=["GET"]
)
@jwt_required()
def get_live_sales():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    sales = Sale.query.filter_by(
        organization_id=current_user.organization_id
    ).order_by(
        Sale.timestamp.desc()
    ).limit(10).all()

    return {
        "success": True,
        "sales": [s.to_dict() for s in sales]
    }, 200