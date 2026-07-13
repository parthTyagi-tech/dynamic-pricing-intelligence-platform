import uuid

from datetime import datetime, timezone

from app.extensions import db


class Organization(db.Model):

    __tablename__ = "organizations"

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    name = db.Column(
        db.String(255),
        nullable=False
    )

    invite_code = db.Column(
        db.String(64),
        unique=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    onboarding_completed = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    store_platform = db.Column(
        db.String(64),
        nullable=True
    )

    store_domain = db.Column(
        db.String(255),
        nullable=True
    )

    # =========================
    # Relationships
    # =========================

    users = db.relationship(
        "User",
        back_populates="organization",
        lazy="dynamic"
    )

    products = db.relationship(
        "Product",
        back_populates="organization",
        lazy="dynamic"
    )

    recommendations = db.relationship(
        "PricingRecommendation",
        back_populates="organization",
        lazy="dynamic"
    )

    audit_logs = db.relationship(
        "AuditLog",
        back_populates="organization",
        lazy="dynamic"
    )

    pricing_rules = db.relationship(
        "PricingRule",
        back_populates="organization",
        uselist=False
    )

    # =========================
    # Utility Methods
    # =========================

    def to_dict(self):

        return {
            "id": self.id,
            "name": self.name,
            "invite_code": self.invite_code,
            "onboarding_completed": self.onboarding_completed,
            "store_platform": self.store_platform,
            "store_domain": self.store_domain,
            "created_at": self.created_at.isoformat(),
        }

    @staticmethod
    def generate_invite_code():

        return str(uuid.uuid4()).replace("-", "")[:12].upper()