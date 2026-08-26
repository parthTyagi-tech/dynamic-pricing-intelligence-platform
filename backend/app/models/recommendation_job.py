from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.extensions import db


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RecommendationJobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"

    ALL = [QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELED]


class AgentRunStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"

    ALL = [PENDING, RUNNING, SUCCEEDED, FAILED, SKIPPED]


class RecommendationJob(db.Model):
    __tablename__ = "recommendation_jobs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recommendation_id = db.Column(db.String(36), db.ForeignKey("pricing_recommendations.id"), nullable=False, unique=True, index=True)
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=False, index=True)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False, index=True)
    status = db.Column(db.String(24), nullable=False, default=RecommendationJobStatus.QUEUED, index=True)
    progress = db.Column(db.Integer, nullable=False, default=0)
    current_agent = db.Column(db.String(64), nullable=True)
    requested_platforms = db.Column(db.JSON, nullable=False, default=list)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    worker_id = db.Column(db.String(128), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    available_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    locked_at = db.Column(db.DateTime, nullable=True)
    last_heartbeat_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    recommendation = db.relationship("PricingRecommendation", back_populates="job", uselist=False)
    product = db.relationship("Product", back_populates="recommendation_jobs")
    organization = db.relationship("Organization", back_populates="recommendation_jobs")
    events = db.relationship("RecommendationAgentEvent", back_populates="job", cascade="all, delete-orphan", order_by="RecommendationAgentEvent.created_at")
    offers = db.relationship("MarketplaceOffer", back_populates="job", cascade="all, delete-orphan", order_by="MarketplaceOffer.platform")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "recommendation_id": self.recommendation_id,
            "product_id": self.product_id,
            "organization_id": self.organization_id,
            "status": self.status,
            "progress": self.progress,
            "current_agent": self.current_agent,
            "requested_platforms": self.requested_platforms or [],
            "attempts": self.attempts,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "events": [event.to_dict() for event in self.events],
            "offers": [offer.to_dict() for offer in self.offers],
            "recommendation": self.recommendation.to_dict() if self.recommendation else None,
        }


class RecommendationAgentEvent(db.Model):
    __tablename__ = "recommendation_agent_events"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = db.Column(db.String(36), db.ForeignKey("recommendation_jobs.id"), nullable=False, index=True)
    agent_name = db.Column(db.String(64), nullable=False, index=True)
    status = db.Column(db.String(24), nullable=False, default=AgentRunStatus.PENDING)
    progress = db.Column(db.Integer, nullable=False, default=0)
    message = db.Column(db.Text, nullable=False)
    payload = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    job = db.relationship("RecommendationJob", back_populates="events")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "payload": self.payload or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MarketplaceOffer(db.Model):
    __tablename__ = "marketplace_offers"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = db.Column(db.String(36), db.ForeignKey("recommendation_jobs.id"), nullable=False, index=True)
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=False, index=True)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False, index=True)
    platform = db.Column(db.String(64), nullable=False, index=True)
    title = db.Column(db.Text, nullable=True)
    brand = db.Column(db.String(128), nullable=True)
    variant = db.Column(db.String(255), nullable=True)
    current_price = db.Column(db.Float, nullable=True)
    mrp = db.Column(db.Float, nullable=True)
    availability = db.Column(db.String(64), nullable=True)
    in_stock = db.Column(db.Boolean, nullable=True)
    specifications = db.Column(db.JSON, nullable=True)
    images = db.Column(db.JSON, nullable=True)
    rating = db.Column(db.Float, nullable=True)
    review_count = db.Column(db.Integer, nullable=True)
    offers = db.Column(db.JSON, nullable=True)
    product_url = db.Column(db.Text, nullable=True)
    match_confidence = db.Column(db.String(16), nullable=True)
    source_type = db.Column(db.String(32), nullable=True)
    fetched_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    job = db.relationship("RecommendationJob", back_populates="offers")
    product = db.relationship("Product")
    organization = db.relationship("Organization")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "product_id": self.product_id,
            "platform": self.platform,
            "title": self.title,
            "brand": self.brand,
            "variant": self.variant,
            "current_price": self.current_price,
            "mrp": self.mrp,
            "availability": self.availability,
            "in_stock": self.in_stock,
            "specifications": self.specifications or {},
            "images": self.images or [],
            "rating": self.rating,
            "review_count": self.review_count,
            "offers": self.offers or [],
            "product_url": self.product_url,
            "match_confidence": self.match_confidence,
            "source_type": self.source_type,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
        }
