import queue
import threading
import time
import logging
from flask import Flask
from app.extensions import db
from app.models.product import Product
from app.models.audit_loging import PricingRule
from app.models.market_data import CompetitorPrice, DemandSignal
from app.models.recommendation import (
    PricingRecommendation,
    RecommendationStatus,
    ApprovalAction,
    ApprovalActionType
)
from app.services.email_service import send_recommendation_action_email
from app.services.whatsapp_service import send_whatsapp_recommendation_action
from app.models.user import User
from app.services.ai_pricing_service import PricingStrategyAgent
import random

logger = logging.getLogger(__name__)

# Thread-safe queue
task_queue = queue.Queue()

# Thread context management
flask_app_ref = None

def init_worker(app: Flask):
    """Start the background worker thread."""
    global flask_app_ref
    flask_app_ref = app
    
    worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="KlypupTaskWorker")
    worker_thread.start()
    logger.info("[task_worker] Background task worker initialized and started.")

def enqueue_pricing_recommendation(recommendation_id: str, product_id: str):
    """Add a recommendation generation job to the queue."""
    task_queue.put({
        "recommendation_id": recommendation_id,
        "product_id": product_id
    })
    logger.info(f"[task_worker] Enqueued pricing task for product {product_id} (Recommendation {recommendation_id})")

def _worker_loop():
    """Persistent loop running in a background thread."""
    while True:
        try:
            # Block until a job is available
            job = task_queue.get()
            rec_id = job["recommendation_id"]
            prod_id = job["product_id"]
            
            logger.info(f"[task_worker] Starting processing of recommendation {rec_id} for product {prod_id}...")
            
            # Execute inside Flask application context
            with flask_app_ref.app_context():
                _process_pricing_job(rec_id, prod_id)
                
            task_queue.task_done()
            
            # Small cooldown delay to prevent immediate Groq rate limit overlap on sequential batch actions
            time.sleep(1.0)
            
        except Exception as e:
            logger.error(f"[task_worker] Worker loop error: {e}", exc_info=True)
            time.sleep(2.0)

def _process_pricing_job(recommendation_id: str, product_id: str):
    """Loads database records, triggers agents, updates the recommendation status."""
    recommendation = PricingRecommendation.query.get(recommendation_id)
    product = Product.query.get(product_id)
    
    if not recommendation or not product:
        logger.error(f"[task_worker] Could not find recommendation {recommendation_id} or product {product_id} in DB.")
        return
        
    try:
        # Run real-time scraper if no competitor price records exist yet
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

        # Run AI Pricing strategy orchestrator
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

        # Update recommendation properties
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

        # Auto-execute checking
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
            db.session.flush() # flush to get approval_action.id
            recommendation.ai_summary += " (AUTOPILOT: Automatically executed due to high confidence)"
            
            # Send Notification for auto-execute
            try:
                # Find the owner/admin user to notify
                admin_user = User.query.filter_by(organization_id=product.organization_id, role="admin").first()
                if admin_user:
                    product_details = {"name": product.name, "sku": product.sku}
                    rec_details = {
                        "id": recommendation.id,
                        "previous_price": previous_price,
                        "executed_price": recommendation.recommended_price,
                        "rationale": recommendation.rationale,
                        "confidence_score": recommendation.confidence_score
                    }
                    comp_prices = [{"competitor_name": cp.competitor_name, "competitor_price": cp.competitor_price, "in_stock": cp.in_stock} for cp in product.competitor_prices.all()]
                    
                    send_recommendation_action_email(
                        user_email=admin_user.email,
                        action_type="auto_execute",
                        product_details=product_details,
                        recommendation_details=rec_details,
                        competitor_prices=comp_prices,
                        action_id=approval_action.id
                    )
                    if admin_user.phone_number:
                        send_whatsapp_recommendation_action(
                            phone_number=admin_user.phone_number,
                            action_type="auto_execute",
                            product_details=product_details,
                            recommendation_details=rec_details,
                            competitor_prices=comp_prices
                        )
            except Exception as e:
                logger.error(f"[task_worker] Failed to send auto-execute notification: {e}")
        
        db.session.commit()
        logger.info(f"[task_worker] Successfully completed pricing generation for recommendation {recommendation_id}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[task_worker] Failed processing recommendation {recommendation_id}: {e}", exc_info=True)
        # Mark recommendation as failed
        recommendation.status = RecommendationStatus.FAILED
        recommendation.rationale = f"Generation failed: {str(e)}"
        db.session.commit()
