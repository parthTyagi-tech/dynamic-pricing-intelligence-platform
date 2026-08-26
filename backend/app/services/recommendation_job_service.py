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
    category = (product.category_hint or product.category or "").strip().lower()
    for key, platforms in CATEGORY_PLATFORM_ROUTING.items():
        if key in category:
            routed = [platform for platform in platforms if platform in SUPPORTED_MARKETPLACES]
            return routed or FALLBACK_PLATFORMS
    return FALLBACK_PLATFORMS


def create_recommendation_job(product: Product, organization_id: str) -> tuple[PricingRecommendation, RecommendationJob]:
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
        requested_platforms=platforms_for_product(product),
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
