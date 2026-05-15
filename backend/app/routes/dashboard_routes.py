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