import random

from flask import Blueprint

from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity
)

from app.extensions import db

from app.models.user import User

from app.models.product import Product

from app.models.market_data import (
    CompetitorPrice,
    DemandSignal
)

from app.models.recommendation import (
    PricingRecommendation
)

from app.services.ai_pricing_service import (
    MarketIntelligenceAgent,
    DemandForecastAgent,
    InventoryAgent,
    PricingStrategyAgent
)


recommendation_bp = Blueprint(
    "recommendations",
    __name__
)


# =====================================
# GENERATE AI RECOMMENDATION
# =====================================

@recommendation_bp.route(
    "/generate/<product_id>",
    methods=["POST"]
)
@jwt_required()
def generate_recommendation(product_id):

    current_user_id = get_jwt_identity()

    current_user = User.query.get(
        current_user_id
    )

    if not current_user:

        return {
            "success": False,
            "message": "User not found"
        }, 404

    product = Product.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()

    if not product:

        return {
            "success": False,
            "message": "Product not found"
        }, 404

    try:

        # =====================================
        # MULTI AGENT ANALYSIS
        # =====================================

        market_data = MarketIntelligenceAgent.analyze(
            product
        )

        demand_data = DemandForecastAgent.analyze(
            product
        )

        inventory_data = InventoryAgent.analyze(
            product
        )

        # =====================================
        # STORE MARKET DATA
        # =====================================

        competitor_data = CompetitorPrice(

            competitor_name="AI Market Agent",

            competitor_price=market_data[
                "competitor_price"
            ],

            product_id=product.id,

            organization_id=current_user.organization_id
        )

        demand_signal = DemandSignal(

            trend_score=demand_data[
                "demand_score"
            ] / 100,

            seasonal_factor=1.1,

            sku_velocity=random.uniform(
                10,
                100
            ),

            product_id=product.id,

            organization_id=current_user.organization_id
        )

        db.session.add(competitor_data)

        db.session.add(demand_signal)

        # =====================================
        # AI PRICING STRATEGY
        # =====================================

        ai_result = PricingStrategyAgent.generate(

            product,

            market_data,

            demand_data,

            inventory_data
        )

        # =====================================
        # CREATE RECOMMENDATION
        # =====================================

        recommendation = PricingRecommendation(

            product_id=product.id,

            recommended_price=ai_result[
                "recommended_price"
            ],

            confidence_score=ai_result[
                "confidence_score"
            ],

            rationale=ai_result[
                "rationale"
            ],

            ai_summary=ai_result[
                "ai_summary"
            ],

            created_by_agent="PricingStrategyAgent",

            # =====================================
            # SAVE EXPLAINABILITY DATA
            # =====================================

            agent_analysis={

                "market_agent": market_data,

                "demand_agent": demand_data,

                "inventory_agent": inventory_data
            },

            organization_id=current_user.organization_id
        )

        db.session.add(recommendation)

        db.session.commit()

        return {

            "success": True,

            "message":
            "AI recommendation generated successfully",

            "recommendation":
            recommendation.to_dict()

        }, 201

    except Exception as e:

        db.session.rollback()

        return {

            "success": False,

            "message": str(e)

        }, 500


# =====================================
# GET ALL RECOMMENDATIONS
# =====================================

@recommendation_bp.route(
    "",
    methods=["GET"]
)
@jwt_required()
def get_recommendations():

    current_user_id = get_jwt_identity()

    current_user = User.query.get(
        current_user_id
    )

    if not current_user:

        return {
            "success": False,
            "message": "User not found"
        }, 404

    recommendations = PricingRecommendation.query.filter_by(
        organization_id=current_user.organization_id
    ).order_by(
        PricingRecommendation.created_at.desc()
    ).all()

    return {

        "success": True,

        "count": len(recommendations),

        "recommendations": [

            recommendation.to_dict()

            for recommendation in recommendations
        ]

    }, 200