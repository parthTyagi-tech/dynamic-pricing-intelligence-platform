from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.extensions import db
from app.models.product import Product
from app.models.recommendation import PricingRecommendation
from app.models.recommendation_job import (
    AgentRunStatus,
    RecommendationAgentEvent,
    RecommendationJob,
    RecommendationJobStatus,
)


CATEGORY_PLATFORM_ROUTING: dict[str, list[str]] = {
    "electronics": ["Amazon", "Flipkart", "Croma", "Reliance Digital", "Vijay Sales"],
    "electronics & gadgets": ["Amazon", "Flipkart", "Croma", "Reliance Digital", "Vijay Sales"],
    "apparel": ["Myntra", "Ajio", "Tata CLiQ", "Nykaa Fashion", "H&M", "Amazon Fashion"],
    "fashion": ["Myntra", "Ajio", "Tata CLiQ", "Nykaa Fashion", "H&M", "Amazon Fashion"],
    "beauty": ["Nykaa", "Purplle", "Sephora", "Amazon"],
    "home_goods": ["Pepperfry", "Urban Ladder", "IKEA", "Home Centre", "Amazon"],
    "home": ["Pepperfry", "Urban Ladder", "IKEA", "Home Centre", "Amazon"],
    "sports": ["Decathlon", "Amazon", "Flipkart Sports"],
    "sports & fitness": ["Decathlon", "Amazon", "Flipkart Sports"],
    "grocery": ["BigBasket", "JioMart", "Blinkit", "Zepto", "Amazon Fresh"],
    "books": ["Amazon", "Flipkart", "Crossword", "Sapna Book House"],
    "toys": ["FirstCry", "Amazon", "Flipkart"],
    "automotive": ["Boodmo", "CarTrade", "Amazon Automotive"],
    "pharmacy": ["1mg", "PharmEasy", "Netmeds", "Apollo Pharmacy"],
    "jewelry": ["Tanishq", "CaratLane", "Titan", "Amazon"],
    "pet": ["Heads Up For Tails", "Amazon", "Supertails"],
}

SUPPORTED_MARKETPLACES = {"Amazon", "Flipkart", "Ajio", "Croma", "Myntra", "Nykaa", "Reliance Digital", "Tata CLiQ"}
FALLBACK_PLATFORMS = ["Amazon", "Flipkart"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def platforms_for_product(product: Product) -> list[str]:
    category = (getattr(product, "category_hint", None) or getattr(product, "category", None) or "").strip().lower()
    for key, platforms in CATEGORY_PLATFORM_ROUTING.items():
        if key in category:
            routed = [platform for platform in platforms if platform in SUPPORTED_MARKETPLACES]
            return routed or FALLBACK_PLATFORMS
    return FALLBACK_PLATFORMS


def create_recommendation_job(
    product: Product,
    organization_id: str,
    requested_platforms: list[str] | None = None
) -> tuple[PricingRecommendation, RecommendationJob]:
    recommendation = PricingRecommendation(
        product_id=product.id,
        recommended_price=float(product.current_price or 0),
        confidence_score=0.0,
        rationale="Initializing evidence-backed pricing analysis.",
        ai_summary="Queued for asynchronous marketplace research.",
        status="processing",
        created_by_agent="OrchestratorAgent",
        organization_id=organization_id,
    )
    db.session.add(recommendation)
    db.session.flush()
    job = RecommendationJob(
        recommendation_id=recommendation.id,
        product_id=product.id,
        organization_id=organization_id,
        status=RecommendationJobStatus.QUEUED,
        progress=0,
        current_agent="OrchestratorAgent",
        requested_platforms=requested_platforms,
    )
    db.session.add(job)
    db.session.flush()
    emit_event(job, "orchestrator", AgentRunStatus.PENDING, 0, "Recommendation job queued for durable processing.", commit=False)
    db.session.commit()
    return recommendation, job


def emit_event(job: RecommendationJob, agent_name: str, status: str, progress: int, message: str, payload: dict[str, Any] | None = None, *, commit: bool = True) -> RecommendationAgentEvent:
    job.current_agent = agent_name
    job.progress = max(0, min(100, int(progress)))
    job.updated_at = utcnow()
    event = RecommendationAgentEvent(
        job_id=job.id,
        agent_name=agent_name,
        status=status,
        progress=job.progress,
        message=message,
        payload=payload or {},
    )
    db.session.add(event)
    if commit:
        db.session.commit()
    return event


def mark_job_failed(job: RecommendationJob, message: str) -> None:
    job.status = RecommendationJobStatus.FAILED
    job.error_message = message[:4000]
    job.completed_at = utcnow()
    emit_event(job, "orchestrator", AgentRunStatus.FAILED, job.progress, message)
    db.session.commit()


def mark_job_succeeded(job: RecommendationJob) -> None:
    job.status = RecommendationJobStatus.SUCCEEDED
    job.progress = 100
    job.current_agent = "orchestrator"
    job.completed_at = utcnow()
    job.updated_at = utcnow()
    db.session.commit()


def execute_auto_approval(recommendation: PricingRecommendation, product: Product, ai_result: dict[str, Any]) -> bool:
    """
    Single source of truth for the auto-execute path. Returns True if the
    recommendation was auto-executed, False if it was downgraded to PENDING
    (e.g. SEC-10 violation) instead. Called from both task_worker.py and
    recommendation_routes.py — must never be reimplemented at either call site.
    """
    import logging
    logger = logging.getLogger(__name__)
    from app.models.price_history import PriceHistory
    from app.models.recommendation import ApprovalAction, ApprovalActionType, RecommendationStatus
    from app.utils.security_guardrails import atomic_ledger_write, check_sanity_bound

    flagged, delta_pct = check_sanity_bound(product.current_price, recommendation.recommended_price)

    if flagged:
        recommendation.status = RecommendationStatus.PENDING
        recommendation.sanity_bound_flagged = True
        recommendation.rationale = (
            (recommendation.rationale or "")
            + f" [SEC-10 SANITY BOUND FLAGGED: {delta_pct:.1%} exceeds 50%. "
              "Auto-execution blocked; requires human review.]"
        )
        logger.warning(
            f"[auto_approval] Blocked auto-execute for recommendation {recommendation.id}: "
            f"delta {delta_pct:.1%} exceeds SEC-10 bound."
        )
        db.session.commit()
        return False

    with atomic_ledger_write():
        previous_price = product.current_price
        recommendation.status = RecommendationStatus.APPROVED
        recommendation.sanity_bound_flagged = False
        product.current_price = recommendation.recommended_price

        approval_action = ApprovalAction(
            recommendation_id=recommendation.id,
            action_type=ApprovalActionType.AUTO_EXECUTE,
            previous_price=previous_price,
            executed_price=recommendation.recommended_price,
            approved_by=None,
            timestamp=recommendation.created_at,
        )
        db.session.add(approval_action)

        db.session.add(PriceHistory(
            product_id=product.id,
            organization_id=product.organization_id,
            old_price=previous_price,
            new_price=recommendation.recommended_price,
            platform_prices=recommendation.platform_prices_snapshot or {},
            approved_by=None,
            recommendation_id=recommendation.id,
        ))
        db.session.flush()

    recommendation.ai_summary = (recommendation.ai_summary or "") + \
        " (AUTOPILOT: Automatically executed due to high confidence)"
    db.session.commit()

    _send_auto_execute_notification(recommendation, product, approval_action)
    return True


def _send_auto_execute_notification(recommendation: PricingRecommendation, product: Product, approval_action: Any) -> None:
    """
    Extracted notification sender for auto-execute. Uses recommendation's
    platform_prices_snapshot rather than the nonexistent product.competitor_prices.
    """
    import logging
    logger = logging.getLogger(__name__)
    try:
        from app.models.user import User
        from app.services.email_service import send_recommendation_action_email
        from app.services.whatsapp_service import send_whatsapp_recommendation_action

        admin_user = User.query.filter_by(
            organization_id=product.organization_id, role="admin"
        ).first()
        if not admin_user:
            return

        snapshot = recommendation.platform_prices_snapshot or {}
        comp_prices = [
            {
                "competitor_name": name,
                "competitor_price": data.get("price"),
                "in_stock": data.get("in_stock", data.get("stock_status") == "in_stock"),
            }
            for name, data in snapshot.items()
            if isinstance(data, dict)
        ]

        product_details = {"name": product.name, "sku": product.sku}
        rec_details = {
            "id": recommendation.id,
            "previous_price": approval_action.previous_price,
            "executed_price": recommendation.recommended_price,
            "rationale": recommendation.rationale,
            "confidence_score": recommendation.confidence_score,
        }

        send_recommendation_action_email(
            user_email=admin_user.email, action_type="auto_execute",
            product_details=product_details, recommendation_details=rec_details,
            competitor_prices=comp_prices, action_id=approval_action.id,
        )
        if admin_user.phone_number:
            send_whatsapp_recommendation_action(
                phone_number=admin_user.phone_number, action_type="auto_execute",
                product_details=product_details, recommendation_details=rec_details,
                competitor_prices=comp_prices,
            )
    except Exception as e:
        logger.error(f"[auto_approval] Failed to send auto-execute notification: {e}")

