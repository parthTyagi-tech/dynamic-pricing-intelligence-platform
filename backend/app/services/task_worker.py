import queue
import threading
from datetime import datetime, timezone, timedelta
import time
import logging
from flask import Flask
from app.extensions import db
from app.models.product import Product
from app.models.audit_loging import PricingRule
from app.models.market_data import DemandSignal, Sale
from app.models.recommendation import (
    PricingRecommendation,
    RecommendationStatus,
    ApprovalAction,
    ApprovalActionType
)
from app.models.recommendation_job import AgentRunStatus, MarketplaceOffer, RecommendationJob, RecommendationJobStatus
from app.services.recommendation_job_service import (
    emit_event,
    mark_job_failed,
    mark_job_succeeded,
    execute_auto_approval,
)
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
        # Always run agentic scraper pipeline to fetch fresh competitor prices
        import asyncio
        import uuid
        from app.services.agentic.supervisor_agent import SupervisorAgent
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        supervisor = SupervisorAgent()
        target_platforms = list(job.requested_platforms) if (job and job.requested_platforms) else None
        task_id = str(uuid.uuid4())
        res = loop.run_until_complete(
            supervisor.execute(
                task_id=task_id,
                product_id=product.id,
                organization_id=product.organization_id,
                force_refresh=True,
                target_platforms=target_platforms
            )
        )
        
        rec_dict = res.get("recommendation") or {}
        snapshot = rec_dict.get("platform_prices_snapshot") or {}
        recommendation.platform_prices_snapshot = snapshot
        
        if job:
            MarketplaceOffer.query.filter_by(job_id=job.id).delete()
            for comp_name, comp_data in snapshot.items():
                if isinstance(comp_data, dict):
                    price_val = float(comp_data.get("price", 0) or 0)
                    if price_val <= 0:
                        continue
                    rating_val = None
                    try:
                        rating_val = float(comp_data.get("rating")) if comp_data.get("rating") is not None else None
                    except (ValueError, TypeError):
                        pass

                    specs = {
                        "rating": rating_val,
                        "review_count": comp_data.get("review_count"),
                        "seller": comp_data.get("seller"),
                        "scrape_mode": comp_data.get("scrape_mode", "live_scrape"),
                        "match_score": comp_data.get("match_score"),
                        "latency_ms": comp_data.get("latency_ms"),
                    }

                    db.session.add(MarketplaceOffer(
                        job_id=job.id,
                        product_id=product.id,
                        organization_id=product.organization_id,
                        platform=comp_name,
                        title=comp_data.get("product_title", f"Verified match on {comp_name}"),
                        current_price=price_val,
                        mrp=float(comp_data.get("mrp")) if comp_data.get("mrp") else None,
                        availability="in_stock" if comp_data.get("stock_status") == "in_stock" else "out_of_stock",
                        in_stock=(comp_data.get("stock_status") == "in_stock"),
                        rating=rating_val,
                        review_count=comp_data.get("review_count"),
                        specifications=specs,
                        product_url=comp_data.get("product_url", ""),
                        match_confidence="high" if float(comp_data.get("match_score", 0) or 0) >= 0.8 else "medium",
                        source_type=comp_data.get("data_source", "live_scrape"),
                    ))
            db.session.commit()
            emit_event(job, "scraper", AgentRunStatus.SUCCEEDED, 50, f"Scraper agents verified {len(snapshot)} marketplace result(s).", {"marketplaces": list(snapshot)})

        # Run AI Pricing strategy orchestrator
        if job:
            emit_event(job, "market", AgentRunStatus.RUNNING, 60, "Market agent is comparing verified marketplace evidence.")
        ai_result = PricingStrategyAgent.generate(product)
        
        market_data = ai_result["agent_analysis"]["market_agent"]
        demand_data = ai_result["agent_analysis"]["demand_agent"]
        inventory_data = ai_result["agent_analysis"]["inventory_agent"]

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

        # Auto-execute checking (SEC-10 gated single source of truth)
        if ai_result.get("execution_route") == "auto_execute":
            execute_auto_approval(recommendation, product, ai_result)
        
        db.session.commit()
        if job:
            mark_job_succeeded(job)
            emit_event(job, "orchestrator", AgentRunStatus.SUCCEEDED, 100, "All agents completed; recommendation is ready for review.")
        logger.info(f"[task_worker] Successfully completed pricing generation for recommendation {recommendation_id}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[task_worker] Failed processing recommendation {recommendation_id}: {e}", exc_info=True)
        try:
            rec = PricingRecommendation.query.get(recommendation_id)
            if rec:
                rec.status = RecommendationStatus.FAILED
                rec.rationale = f"Generation failed: {str(e)}"
                db.session.commit()
            j = RecommendationJob.query.filter_by(recommendation_id=recommendation_id).first()
            if j:
                mark_job_failed(j, str(e))
        except Exception as inner_e:
            logger.error(f"[task_worker] Failed to record failure state: {inner_e}", exc_info=True)


process_pricing_recommendation_task = _process_pricing_job

