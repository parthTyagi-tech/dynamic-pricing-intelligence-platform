import uuid

from datetime import datetime, timezone

from app.extensions import db


# =====================================
# RECOMMENDATION STATUS
# =====================================

class RecommendationStatus:

    PENDING = "pending"

    APPROVED = "approved"

    REJECTED = "rejected"

    MODIFIED = "modified"

    EXECUTED = "executed"

    FAILED = "failed"

    ALL = [
        PENDING,
        APPROVED,
        REJECTED,
        MODIFIED,
        EXECUTED,
        FAILED
    ]


# =====================================
# APPROVAL ACTION TYPES
# =====================================

class ApprovalActionType:

    APPROVE = "approve"

    REJECT = "reject"

    MODIFY = "modify"

    AUTO_EXECUTE = "auto_execute"

    ALL = [
        APPROVE,
        REJECT,
        MODIFY,
        AUTO_EXECUTE
    ]


# =====================================
# PRICING RECOMMENDATION MODEL
# =====================================

class PricingRecommendation(db.Model):

    __tablename__ = "pricing_recommendations"

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    product_id = db.Column(
        db.String(36),
        db.ForeignKey("products.id"),
        nullable=False,
        index=True
    )

    recommended_price = db.Column(
        db.Float,
        nullable=False
    )

    confidence_score = db.Column(
        db.Float,
        nullable=False,
        default=0.0
    )

    rationale = db.Column(
        db.Text,
        nullable=True
    )

    status = db.Column(
        db.String(32),
        nullable=False,
        default=RecommendationStatus.PENDING,
        index=True
    )

    ai_summary = db.Column(
        db.Text,
        nullable=True
    )

    created_by_agent = db.Column(
        db.String(128),
        nullable=True
    )

    # =====================================
    # EXPLAINABILITY STORAGE
    # =====================================

    agent_analysis = db.Column(
        db.JSON,
        nullable=True
    )

    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id"),
        nullable=False,
        index=True
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    # =====================================
    # RELATIONSHIPS
    # =====================================

    product = db.relationship(
        "Product",
        back_populates="recommendations"
    )

    organization = db.relationship(
        "Organization",
        back_populates="recommendations"
    )

    approval_actions = db.relationship(
        "ApprovalAction",
        back_populates="recommendation",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    # =====================================
    # SERIALIZER
    # =====================================

    def to_dict(self):

        return {

            "id":
            self.id,

            "product_id":
            self.product_id,

            "recommended_price":
            round(
                float(self.recommended_price),
                2
            ),

            "confidence_score":
            round(
                float(self.confidence_score),
                0
            ),

            "rationale":
            self.rationale,

            "status":
            self.status,

            "ai_summary":
            self.ai_summary,

            "created_by_agent":
            self.created_by_agent,

            # =====================================
            # EXPLAINABILITY DATA
            # =====================================

            "agent_analysis":
            self.agent_analysis,

            "organization_id":
            self.organization_id,

            "created_at":
            self.created_at.isoformat()
            if self.created_at else None,

            "product": {

                "id":
                self.product.id,

                "name":
                self.product.name,

                "sku":
                self.product.sku,

                "current_price":
                round(
                    float(self.product.current_price),
                    2
                )
                if self.product
                and self.product.current_price
                else 0

            } if self.product else None
        }


# =====================================
# APPROVAL ACTION MODEL
# =====================================

class ApprovalAction(db.Model):

    __tablename__ = "approval_actions"

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    recommendation_id = db.Column(
        db.String(36),
        db.ForeignKey("pricing_recommendations.id"),
        nullable=False,
        index=True
    )

    action_type = db.Column(
        db.String(32),
        nullable=False
    )

    previous_price = db.Column(
        db.Float,
        nullable=True
    )

    executed_price = db.Column(
        db.Float,
        nullable=True
    )

    approved_by = db.Column(
        db.String(36),
        db.ForeignKey("users.id"),
        nullable=True
    )

    rejection_reason = db.Column(
        db.Text,
        nullable=True
    )

    timestamp = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    # =====================================
    # RELATIONSHIPS
    # =====================================

    recommendation = db.relationship(
        "PricingRecommendation",
        back_populates="approval_actions"
    )

    approver = db.relationship(
        "User",
        back_populates="approval_actions"
    )

    # =====================================
    # SERIALIZER
    # =====================================

    def to_dict(self):

        return {

            "id":
            self.id,

            "recommendation_id":
            self.recommendation_id,

            "action_type":
            self.action_type,

            "previous_price":
            round(
                float(self.previous_price),
                2
            )
            if self.previous_price
            else None,

            "executed_price":
            round(
                float(self.executed_price),
                2
            )
            if self.executed_price
            else None,

            "approved_by":
            self.approved_by,

            "approver_name":
            self.approver.name
            if self.approver else None,

            "rejection_reason":
            self.rejection_reason,

            "timestamp":
            self.timestamp.isoformat()
            if self.timestamp else None,

            # =====================================
            # PRODUCT DETAILS
            # =====================================

            "product": {

                "id":
                self.recommendation.product.id,

                "name":
                self.recommendation.product.name,

                "sku":
                self.recommendation.product.sku

            } if self.recommendation
            and self.recommendation.product
            else None
        }