import random

from flask import Blueprint, request

from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity
)

from app.extensions import db

from app.models.user import User

from app.models.product import Product

from app.models.market_data import (
    CompetitorPrice,
    DemandSignal,
    Sale
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
# STREAM REAL-TIME MULTI-PLATFORM PRICES (SSE)
# =====================================

@recommendation_bp.route("/stream-scrape/<product_id>", methods=["GET"])
@jwt_required()
def stream_scrape(product_id):
    from flask import Response, stream_with_context
    import asyncio
    from app.services.realtime_scraper import stream_multi_platform_prices

    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    product = Product.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()
    if not product:
        return {"success": False, "message": "Product not found"}, 404

    def generate():
        # Setup async loop inside the thread that Flask uses to stream
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async_gen = stream_multi_platform_prices(
            search_query=product.name, 
            brand=product.brand or "", 
            category=product.category or "", 
            baseline_price_inr=product.current_price or 0.0, 
            barcode=product.barcode or "",
            description=product.description or "",
            product_id=product.id
        )
        
        # Manually iterate through the async generator synchronously using run_until_complete
        # so Flask can yield it normally.
        while True:
            try:
                # __anext__ gets the next chunk
                chunk = loop.run_until_complete(async_gen.__anext__())
                yield chunk
            except StopAsyncIteration:
                break
            except Exception as e:
                import json
                print(f"[SSE Error] {e}")
                yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
                break
        
        loop.close()

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


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
    current_user = User.query.get(current_user_id)

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
        # (Scraping moved to background task worker to prevent frontend timeout)

        # Create a pending recommendation with status = 'processing'
        recommendation = PricingRecommendation(
            product_id=product.id,
            recommended_price=product.current_price,
            confidence_score=0.0,
            rationale="Initializing pricing analysis...",
            ai_summary="Asynchronous pricing analysis initiated.",
            status="processing",
            organization_id=current_user.organization_id
        )
        db.session.add(recommendation)
        db.session.commit()

        # Dispatch background GCP Cloud Task
        from app.services.gcp_tasks_service import create_pricing_recommendation_task
        task_name = create_pricing_recommendation_task(recommendation.id, product.id)

        # Fallback to local in-memory worker queue if GCP Tasks is not configured (local dev)
        if not task_name:
            print("[recommendation_bp] Fallback to local task worker queue.")
            from app.services.task_worker import enqueue_pricing_recommendation
            enqueue_pricing_recommendation(recommendation.id, product.id)

        return {
            "success": True,
            "message": "Pricing task queued successfully via GCP Tasks" if task_name else "Pricing task queued locally in background worker",
            "recommendation": recommendation.to_dict()
        }, 202

    except Exception as e:
        db.session.rollback()
        print(f"[recommendation_bp] Error: {e}")
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

# =====================================
# PROCESS TASK CALLBACK (GCP Cloud Tasks Endpoint)
# =====================================

@recommendation_bp.route(
    "/process-task",
    methods=["POST"]
)
def process_task():
    payload = request.get_json(silent=True) or {}
    recommendation_id = payload.get("recommendation_id")
    product_id = payload.get("product_id")

    if not recommendation_id or not product_id:
        return {
            "success": False,
            "message": "Missing recommendation_id or product_id"
        }, 400

    recommendation = PricingRecommendation.query.get(recommendation_id)
    product = Product.query.get(product_id)

    if not recommendation or not product:
        return {
            "success": False,
            "message": "Recommendation or Product not found"
        }, 404

    # Double check if already processed
    if recommendation.status != "processing":
        return {
            "success": True,
            "message": "Task already processed or status is not processing"
        }, 200

    try:
        # Check if this is a product with zero competitor prices (e.g. newly created)
        has_competitors = CompetitorPrice.query.filter_by(product_id=product.id).first() is not None
        if not has_competitors:
            import asyncio
            from app.services.realtime_scraper import fetch_multi_platform_prices
            
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            scraped_prices = loop.run_until_complete(
                fetch_multi_platform_prices(
                    search_query=product.name,
                    brand=product.brand,
                    category=product.category,
                    baseline_price_inr=product.current_price,
                    barcode=product.barcode or "",
                    description=product.description or "",
                    product_id=product.id
                )
            )
            
            for comp_name, comp_data in scraped_prices.items():
                cp = CompetitorPrice(
                    competitor_name=comp_name,
                    competitor_price=comp_data["price"] if isinstance(comp_data, dict) else comp_data,
                    in_stock=comp_data.get("in_stock", True) if isinstance(comp_data, dict) else True,
                    product_id=product.id,
                    organization_id=product.organization_id
                )
                db.session.add(cp)
            db.session.commit()

        # Run agent strategy logic
        ai_result = PricingStrategyAgent.generate(product)

        market_data = ai_result["agent_analysis"]["market_agent"]
        demand_data = ai_result["agent_analysis"]["demand_agent"]
        inventory_data = ai_result["agent_analysis"]["inventory_agent"]

        competitor_data = CompetitorPrice(
            competitor_name="AI Market Agent",
            competitor_price=market_data["competitor_price"],
            product_id=product.id,
            organization_id=product.organization_id
        )

        demand_signal = DemandSignal(
            trend_score=demand_data["demand_score"] / 100,
            seasonal_factor=1.1,
            sku_velocity=random.uniform(10, 100),
            product_id=product.id,
            organization_id=product.organization_id
        )

        db.session.add(competitor_data)
        db.session.add(demand_signal)

        # Update recommendation parameters
        recommendation.recommended_price = ai_result["recommended_price"]
        recommendation.confidence_score = ai_result["confidence_score"]
        recommendation.rationale = ai_result["rationale"]
        recommendation.ai_summary = ai_result["ai_summary"]
        recommendation.projected_volume_increase_pct = ai_result.get("projected_volume_increase_pct")
        recommendation.projected_monthly_profit_lift = ai_result.get("projected_monthly_profit_lift")
        recommendation.agent_analysis = {
            "market_agent": market_data,
            "demand_agent": demand_data,
            "inventory_agent": inventory_data,
            "fallback_used": ai_result.get("fallback_used", False)
        }
        recommendation.status = RecommendationStatus.PENDING

        # Auto execution logic
        if ai_result.get("execution_route") == "auto_execute":
            recommendation.status = RecommendationStatus.APPROVED
            previous_price = product.current_price
            product.current_price = recommendation.recommended_price

            approval_action = ApprovalAction(
                recommendation_id=recommendation.id,
                action_type=ApprovalActionType.AUTO_EXECUTE,
                previous_price=previous_price,
                executed_price=recommendation.recommended_price,
                approved_by=None,
                timestamp=recommendation.created_at
            )
            db.session.add(approval_action)
            recommendation.ai_summary += " (AUTOPILOT: Automatically executed due to high confidence)"

        db.session.commit()
        return {
            "success": True,
            "message": "Task processed successfully"
        }, 200

    except Exception as e:
        db.session.rollback()
        recommendation.status = RecommendationStatus.FAILED
        recommendation.rationale = f"Processing error: {str(e)}"
        db.session.commit()
        print(f"[recommendation_bp] Task processing error: {e}")
        return {
            "success": False,
            "message": f"Task processing error: {str(e)}"
        }, 500

# =====================================
# GET RECOMMENDATION STATUS (Polling Endpoint)
# =====================================

@recommendation_bp.route(
    "/status/<recommendation_id>",
    methods=["GET"]
)
@jwt_required()
def get_recommendation_status(recommendation_id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

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

    fallback_used = False
    if recommendation.agent_analysis and isinstance(recommendation.agent_analysis, dict):
        fallback_used = recommendation.agent_analysis.get("fallback_used", False)

    return {
        "success": True,
        "status": recommendation.status,
        "fallback_used": fallback_used,
        "recommendation": recommendation.to_dict()
    }, 200

# =====================================
# GET RECOMMENDATION DETAILS
# =====================================

@recommendation_bp.route(
    "/<string:recommendation_id>/details",
    methods=["GET"]
)
@jwt_required()
def get_recommendation_details(recommendation_id):
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)

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

    product = Product.query.get(recommendation.product_id)
    if not product:
        return {
            "success": False,
            "message": "Product not found"
        }, 404

    # Fetch competitor prices
    competitors = CompetitorPrice.query.filter_by(
        product_id=product.id,
        organization_id=current_user.organization_id
    ).all()

    # Fetch demand signals
    signals = DemandSignal.query.filter_by(
        product_id=product.id,
        organization_id=current_user.organization_id
    ).order_by(DemandSignal.created_at.desc()).all()

    # Fetch sales history
    sales = Sale.query.filter_by(
        product_id=product.id,
        organization_id=current_user.organization_id
    ).order_by(Sale.timestamp.desc()).all()

    return {
        "success": True,
        "recommendation": recommendation.to_dict(),
        "product": product.to_dict(),
        "competitors": [c.to_dict() for c in competitors],
        "demand_signals": [s.to_dict() for s in signals],
        "sales_history": [s.to_dict() for s in sales]
    }, 200