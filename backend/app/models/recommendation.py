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

    projected_volume_increase_pct = db.Column(
        db.Float,
        nullable=True
    )

    projected_monthly_profit_lift = db.Column(
        db.Float,
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

    task_id = db.Column(db.String(64), nullable=True, index=True)
    platform_prices_snapshot = db.Column(db.JSON, nullable=True, default=dict)
    margin_floor_applied = db.Column(db.Boolean, nullable=False, default=False)
    margin_floor_value = db.Column(db.Float, nullable=True)
    sanity_bound_flagged = db.Column(db.Boolean, nullable=False, default=False)
    decided_at = db.Column(db.DateTime, nullable=True)
    decided_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)

    @property
    def reasoning_text(self):
        return self.rationale or self.ai_summary or ""

    @reasoning_text.setter
    def reasoning_text(self, val):
        self.rationale = val
        self.ai_summary = val

    @property
    def confidence(self):
        if isinstance(self.confidence_score, (int, float)):
            if self.confidence_score >= 0.85 or self.confidence_score >= 85:
                return "high"
            elif self.confidence_score >= 0.60 or self.confidence_score >= 60:
                return "medium"
            return "low"
        return str(self.confidence_score or "high")

    @confidence.setter
    def confidence(self, val):
        if str(val).lower() == "high":
            self.confidence_score = 0.95
        elif str(val).lower() == "medium":
            self.confidence_score = 0.75
        elif str(val).lower() == "low":
            self.confidence_score = 0.40
        else:
            try:
                self.confidence_score = float(val)
            except Exception:
                self.confidence_score = 0.80

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

    job = db.relationship(
        "RecommendationJob",
        back_populates="recommendation",
        uselist=False,
        cascade="all, delete-orphan"
    )

    price_history = db.relationship(
        "PriceHistory",
        back_populates="recommendation",
        uselist=False
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
        from app.models.market_data import Sale
        
        competitors = []
        sales_history = []
        if self.platform_prices_snapshot and isinstance(self.platform_prices_snapshot, dict):
            for plat, cdata in self.platform_prices_snapshot.items():
                if isinstance(cdata, dict) and cdata.get("price", 0) > 0:
                    competitors.append({
                        "competitor_name": plat,
                        "competitor_price": float(cdata.get("price", 0)),
                        "product_url": cdata.get("product_url", ""),
                        "match_score": float(cdata.get("match_score", 1.0)),
                        "data_source": cdata.get("data_source", "live_scrape")
                    })
        if self.product:
            sales_history = Sale.query.filter_by(
                product_id=self.product_id,
                organization_id=self.organization_id
            ).order_by(Sale.timestamp.desc()).limit(10).all()

        return {

            "id":
            self.id,

            "product_id":
            self.product_id,

            "recommended_price": (
                round(float(self.recommended_price), 2)
                if self.recommended_price is not None
                else 0.0
            ),

            "confidence_score": (
                round(float(self.confidence_score) * (100 if self.confidence_score <= 1.0 else 1), 0)
                if self.confidence_score is not None
                else 0.0
            ),

            "confidence": (
                "high" if (self.confidence_score or 0) >= 0.80 or (self.confidence_score or 0) >= 80
                else ("medium" if (self.confidence_score or 0) >= 0.50 or (self.confidence_score or 0) >= 50 else "low")
            ),

            "rationale":
            self.rationale,

            "status":
            self.status,

            "ai_summary":
            self.ai_summary,

            "created_by_agent":
            self.created_by_agent,

            "agent_analysis":
            self.agent_analysis,

            "organization_id":
            self.organization_id,

            "projected_volume_increase_pct":
            self.projected_volume_increase_pct,

            "projected_monthly_profit_lift":
            self.projected_monthly_profit_lift,

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
                else 0,

                "inventory_quantity":
                self.product.inventory_quantity
                if self.product
                else 0,

                "cost_price":
                round(
                    float(self.product.cost_price),
                    2
                )
                if self.product
                and self.product.cost_price
                else 0

            } if self.product else None,

            "competitors": [c.to_dict() if hasattr(c, "to_dict") else c for c in competitors],
            "sales_history": [s.to_dict() if hasattr(s, "to_dict") else s for s in sales_history],
            "platform_prices_snapshot": self.platform_prices_snapshot or {},
            "margin_floor_applied": bool(self.margin_floor_applied),
            "margin_floor_value": self.margin_floor_value,
            "sanity_bound_flagged": bool(self.sanity_bound_flagged),
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

    sku = db.Column(db.String(128), nullable=True, index=True)
    llm_statement = db.Column(db.Text, nullable=True)
    user_email = db.Column(db.String(255), nullable=True)
    email_sent_status = db.Column(db.String(32), nullable=False, default="pending")
    email_provider_message_id = db.Column(db.String(255), nullable=True)
    email_error = db.Column(db.Text, nullable=True)

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

            "rolled_back":
            self.action_type == "approve" and ApprovalAction.query.filter_by(
                recommendation_id=self.recommendation_id,
                action_type="rollback"
            ).first() is not None,

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
            "sku": self.sku,
            "llm_statement": self.llm_statement,
            "user_email": self.user_email,
            "email_sent_status": self.email_sent_status,
            "email_provider_message_id": self.email_provider_message_id,
            "email_error": self.email_error,

            "timestamp":
            self.timestamp.isoformat()
            if self.timestamp else None,

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