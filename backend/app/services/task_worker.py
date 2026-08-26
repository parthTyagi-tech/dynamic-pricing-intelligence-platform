import queue
import threading
from datetime import datetime, timezone, timedelta
import time
import logging
from flask import Flask
from app.extensions import db
from app.models.product import Product
from app.models.audit_loging import PricingRule
from app.models.market_data import CompetitorPrice, DemandSignal, Sale
from app.models.recommendation import (
    PricingRecommendation,
    RecommendationStatus,
    ApprovalAction,
    ApprovalActionType
)
from app.models.recommendation_job import AgentRunStatus, MarketplaceOffer, RecommendationJob, RecommendationJobStatus
from app.services.recommendation_job_service import emit_event, mark_job_failed, mark_job_succeeded
from app.services.email_service import send_recommendation_action_email
from app.services.whatsapp_service import send_whatsapp_recommendation_action
from app.models.user import User
from app.services.ai_pricing_service import PricingStrategyAgent

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
    job = RecommendationJob.query.filter_by(recommendation_id=recommendation.id).first()
    if job:
        job.status = RecommendationJobStatus.RUNNING
        job.worker_id = "in-process-testing-worker"
        job.attempts = int(job.attempts or 0) + 1
        job.started_at = job.started_at or datetime.now(timezone.utc)
        job.last_heartbeat_at = datetime.now(timezone.utc)
        emit_event(job, "orchestrator", AgentRunStatus.RUNNING, 5, "Local worker claimed the recommendation job.")
        emit_event(job, "scraper", AgentRunStatus.RUNNING, 15, "Scraper agents are searching category-specific marketplaces.")
        
    try:
        # Always run real-time scraper to fetch fresh competitor prices
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
        
        # Capture the last snapshot before replacement so sudden drops can trigger alerts.
        previous_prices = {
            row.competitor_name: float(row.competitor_price)
            for row in CompetitorPrice.query.filter_by(product_id=product.id).all()
            if row.competitor_price
        }

        # Clear existing competitor prices to avoid duplicates/outdated data
        CompetitorPrice.query.filter_by(product_id=product.id).delete()
        if job:
            MarketplaceOffer.query.filter_by(job_id=job.id).delete()
        for comp_name, comp_data in scraped_prices.items():
            value = comp_data if isinstance(comp_data, dict) else {"price": comp_data}
            price_val = float(value.get("price", value.get("price_inr", 0)) or 0)
            if price_val <= 0:
                continue
            cp = CompetitorPrice(
                competitor_name=comp_name,
                competitor_price=price_val,
                in_stock=value.get("in_stock", True),
                product_url=value.get("url", ""),
                product_id=product.id,
                organization_id=product.organization_id
            )
            db.session.add(cp)
            if job:
                db.session.add(MarketplaceOffer(
                    job_id=job.id,
                    product_id=product.id,
                    organization_id=product.organization_id,
                    platform=comp_name,
                    title=value.get("title") or value.get("product_title"),
                    current_price=price_val,
                    availability="in_stock" if value.get("in_stock", True) else "out_of_stock",
                    in_stock=value.get("in_stock", True),
                    product_url=value.get("url", ""),
                    match_confidence=value.get("match_confidence") or "medium",
                    source_type=value.get("fetch_method") or value.get("extraction_strategy") or "live_scrape",
                ))
        db.session.commit()
        if job:
            emit_event(job, "scraper", AgentRunStatus.SUCCEEDED, 50, f"Scraper agents found {len(scraped_prices)} marketplace result(s).", {"marketplaces": list(scraped_prices)})

        # Trigger persistent in-app alerts for meaningful marketplace drops.

        from app.services.price_alert_service import detect_and_create_alerts
        current_prices = {
            comp_name: float(comp_data.get("price", 0) if isinstance(comp_data, dict) else comp_data)
            for comp_name, comp_data in scraped_prices.items()
        }
        drop_alerts = detect_and_create_alerts(product, previous_prices, current_prices)
        if drop_alerts:
            db.session.commit()
            logger.info("[task_worker] Created %s competitor drop alert(s) for %s", len(drop_alerts), product.sku)

        # Run AI Pricing strategy orchestrator
        if job:
            emit_event(job, "market", AgentRunStatus.RUNNING, 60, "Market agent is comparing verified marketplace evidence.")
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
        sales_14d = db.session.query(db.func.coalesce(db.func.sum(Sale.quantity), 0)).filter(
            Sale.product_id == product.id,
            Sale.organization_id == product.organization_id,
            Sale.timestamp >= datetime.now(timezone.utc) - timedelta(days=14)
        ).scalar() or 0
        demand_signal = DemandSignal(
            trend_score=demand_data["demand_score"] / 100,
            seasonal_factor=demand_data.get("seasonal_factor", 1.0),
            sku_velocity=float(sales_14d) / 14.0,
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
        if job:
            emit_event(job, "market", AgentRunStatus.SUCCEEDED, 70, "Market agent completed competitor-price analysis.")
            emit_event(job, "inventory", AgentRunStatus.SUCCEEDED, 85, "Inventory agent completed margin and stock analysis.")
            emit_event(job, "orchestrator", AgentRunStatus.RUNNING, 90, "Orchestrator synthesized the final price recommendation.")

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
        if job:
            mark_job_succeeded(job)
            emit_event(job, "orchestrator", AgentRunStatus.SUCCEEDED, 100, "All agents completed; recommendation is ready for review.")
        logger.info(f"[task_worker] Successfully completed pricing generation for recommendation {recommendation_id}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[task_worker] Failed processing recommendation {recommendation_id}: {e}", exc_info=True)
        # Mark recommendation as failed
        recommendation.status = RecommendationStatus.FAILED
        recommendation.rationale = f"Generation failed: {str(e)}"
        db.session.commit()
        if job:
            mark_job_failed(job, str(e))
