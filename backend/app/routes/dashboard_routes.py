from flask import Blueprint

from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity
)

from app.models.user import User
from app.models.product import Product

from app.models.recommendation import (
    PricingRecommendation,
    RecommendationStatus
)

dashboard_bp = Blueprint(
    "dashboard",
    __name__
)


# =====================================
# DASHBOARD ANALYTICS
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

    total_products = Product.query.filter_by(
        organization_id=current_user.organization_id
    ).count()

    total_recommendations = PricingRecommendation.query.filter_by(
        organization_id=current_user.organization_id
    ).count()

    return {
        "totalRevenue": total_products * 1200,
        "pricingAccuracy": 94,
        "marketVolatility": 21,
        "aiConfidence": 97,
        "competitorChanges": total_recommendations,
        "conversionRate": 18
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

    return [
        {
            "date": "Jan",
            "actual": 1200,
            "predicted": 1400
        },
        {
            "date": "Feb",
            "actual": 1800,
            "predicted": 2000
        },
        {
            "date": "Mar",
            "actual": 2400,
            "predicted": 2600
        },
        {
            "date": "Apr",
            "actual": 3200,
            "predicted": 3500
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

    return [
        {
            "time": "10AM",
            "aiPrice": 120,
            "competitorPrice": 115,
            "marketAverage": 118
        },
        {
            "time": "12PM",
            "aiPrice": 128,
            "competitorPrice": 122,
            "marketAverage": 124
        },
        {
            "time": "2PM",
            "aiPrice": 134,
            "competitorPrice": 130,
            "marketAverage": 132
        }
    ], 200


# =====================================
# DEMAND API
# =====================================

@dashboard_bp.route(
    "/demand",
    methods=["GET"]
)
@jwt_required()
def get_demand():

    return [
        {
            "category": "Electronics",
            "demand": 82
        },
        {
            "category": "Fashion",
            "demand": 64
        },
        {
            "category": "Groceries",
            "demand": 91
        },
        {
            "category": "Accessories",
            "demand": 73
        }
    ], 200


# =====================================
# AI PERFORMANCE API
# =====================================

@dashboard_bp.route(
    "/ai-performance",
    methods=["GET"]
)
@jwt_required()
def get_ai_performance():

    return [
        {
            "metric": "Accuracy",
            "score": 94
        },
        {
            "metric": "Forecasting",
            "score": 91
        },
        {
            "metric": "Optimization",
            "score": 96
        },
        {
            "metric": "Elasticity",
            "score": 89
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

    return [
        {
            "id": 1,
            "productName": "Premium Headphones",
            "confidence": 96,
            "currentPrice": 120,
            "suggestedPrice": 138,
            "reason": "High demand detected"
        },
        {
            "id": 2,
            "productName": "Gaming Mouse",
            "confidence": 92,
            "currentPrice": 80,
            "suggestedPrice": 95,
            "reason": "Competitor prices increased"
        }
    ], 200