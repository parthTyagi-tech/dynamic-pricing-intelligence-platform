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
    PricingRecommendation,
    RecommendationStatus,
    ApprovalAction,
    ApprovalActionType
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

        # Check if this is a product with zero competitor prices (e.g. newly created)
        has_competitors = CompetitorPrice.query.filter_by(product_id=product.id).first() is not None
        if not has_competitors:
            import asyncio
            from app.services.realtime_scraper import fetch_realtime_competitor_prices
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            scraped_prices = loop.run_until_complete(
                fetch_realtime_competitor_prices(product.name, product.current_price)
            )
            
            for comp_name, price in scraped_prices.items():
                cp = CompetitorPrice(
                    competitor_name=comp_name,
                    competitor_price=price,
                    product_id=product.id,
                    organization_id=current_user.organization_id
                )
                db.session.add(cp)
            db.session.commit()

        # =====================================
        # MULTI AGENT ANALYSIS
        # =====================================

        # Execute the entire 5-agent pipeline concurrently in parallel!
        ai_result = PricingStrategyAgent.generate(product)

        market_data = ai_result["agent_analysis"]["market_agent"]
        demand_data = ai_result["agent_analysis"]["demand_agent"]
        inventory_data = ai_result["agent_analysis"]["inventory_agent"]

        competitor_data = CompetitorPrice(
            competitor_name="AI Market Agent",
            competitor_price=market_data["competitor_price"],
            product_id=product.id,
            organization_id=current_user.organization_id
        )

        demand_signal = DemandSignal(
            trend_score=demand_data["demand_score"] / 100,
            seasonal_factor=1.1,
            sku_velocity=random.uniform(10, 100),
            product_id=product.id,
            organization_id=current_user.organization_id
        )

        db.session.add(competitor_data)
        db.session.add(demand_signal)

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

            projected_volume_increase_pct=ai_result.get("projected_volume_increase_pct"),

            projected_monthly_profit_lift=ai_result.get("projected_monthly_profit_lift"),

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
        db.session.flush()

        # =====================================
        # PHASE 1: AUTOPILOT ZERO-CLICK ENGINE
        # =====================================
        if ai_result.get("execution_route") == "auto_execute":
            # 1. Update the status
            recommendation.status = RecommendationStatus.APPROVED

            # 2. Update the actual product price
            previous_price = product.current_price
            product.current_price = recommendation.recommended_price

            # 3. Create an Audit / Approval Action
            approval_action = ApprovalAction(
                recommendation_id=recommendation.id,
                action_type=ApprovalActionType.AUTO_EXECUTE,
                previous_price=previous_price,
                executed_price=recommendation.recommended_price,
                approved_by=None, # System execution
                timestamp=recommendation.created_at
            )
            db.session.add(approval_action)
            # Add note to summary
            recommendation.ai_summary += " (AUTOPILOT: Automatically executed due to high confidence)"
            
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
    organization_id=current_user.organization_id,
    status=RecommendationStatus.PENDING
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


# =====================================
# APPROVE RECOMMENDATION
# =====================================

@recommendation_bp.route(
    "/<string:recommendation_id>/approve",
    methods=["POST"]
)
@jwt_required()
def approve_recommendation(recommendation_id):

    current_user_id = get_jwt_identity()

    current_user = User.query.get(
        current_user_id
    )

    if not current_user:

        return {
            "success": False,
            "message": "User not found"
        }, 404

    recommendation = PricingRecommendation.query.filter_by(
        id=recommendation_id,
        organization_id=current_user.organization_id
    ).first()

    if not recommendation:

        return {
            "success": False,
            "message": "Recommendation not found"
        }, 404

    try:

        recommendation.status = (
            RecommendationStatus.APPROVED
        )

        product = Product.query.get(
            recommendation.product_id
        )

        if product:

            previous_price = (
                product.current_price
            )

            product.current_price = (
                recommendation.recommended_price
            )

            approval_action = ApprovalAction(

                recommendation_id=recommendation.id,

                action_type=ApprovalActionType.APPROVE,

                previous_price=previous_price,

                executed_price=(
                    recommendation.recommended_price
                ),

                approved_by=current_user.id
            )

            db.session.add(
                approval_action
            )

        db.session.commit()

        return {

            "success": True,

            "message":
            "Recommendation approved successfully"

        }, 200

    except Exception as e:

        db.session.rollback()

        return {

            "success": False,

            "message": str(e)

        }, 500