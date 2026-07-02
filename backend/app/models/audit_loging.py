import uuid
from datetime import datetime, timezone
from app.extensions import db


class PricingRule(db.Model):
    __tablename__ = "pricing_rules"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    auto_execute_threshold = db.Column(db.Float, nullable=False, default=0.95)
    minimum_margin = db.Column(db.Float, nullable=False, default=0.10)
    organization_id = db.Column(
        db.String(36), db.ForeignKey("organizations.id"), nullable=False, unique=True, index=True
    )

    # Relationships
    organization = db.relationship("Organization", back_populates="pricing_rules")

    def to_dict(self):
        return {
            "id": self.id,
            "auto_execute_threshold": self.auto_execute_threshold,
            "minimum_margin": self.minimum_margin,
            "organization_id": self.organization_id,
        }


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True, index=True)
    organization_id = db.Column(
        db.String(36), db.ForeignKey("organizations.id"), nullable=False, index=True
    )
    action = db.Column(db.String(255), nullable=False)
    entity_type = db.Column(db.String(128), nullable=True)
    entity_id = db.Column(db.String(36), nullable=True)
    extra_metadata = db.Column(db.JSON, nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    user = db.relationship("User", back_populates="audit_logs")
    organization = db.relationship("Organization", back_populates="audit_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": self.user.name if self.user else "system",
            "organization_id": self.organization_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "metadata": self.extra_metadata,
            "timestamp": self.timestamp.isoformat(),
        }