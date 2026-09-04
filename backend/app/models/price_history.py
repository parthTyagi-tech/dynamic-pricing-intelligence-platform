import uuid
from datetime import datetime, timezone
from app.extensions import db


class PriceHistory(db.Model):
    """
    Immutable, append-only price change ledger.
    Guarantees full historical auditability of catalog price transitions.
    """
    __tablename__ = "price_history"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=False, index=True)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False, index=True)
    old_price = db.Column(db.Float, nullable=False)
    new_price = db.Column(db.Float, nullable=False)
    platform_prices = db.Column(db.JSON, nullable=False, default=dict)
    approved_by = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    recommendation_id = db.Column(db.String(36), db.ForeignKey("pricing_recommendations.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    product = db.relationship("Product", back_populates="price_histories")
    approver = db.relationship("User", foreign_keys=[approved_by])
    recommendation = db.relationship("PricingRecommendation", back_populates="price_history")

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "organization_id": self.organization_id,
            "old_price": round(float(self.old_price), 2),
            "new_price": round(float(self.new_price), 2),
            "price_delta": round(float(self.new_price - self.old_price), 2),
            "percentage_change": round(((self.new_price - self.old_price) / self.old_price) * 100, 2) if self.old_price else 0.0,
            "platform_prices": self.platform_prices or {},
            "approved_by": self.approved_by,
            "approver_name": self.approver.name if self.approver else "Automated / System",
            "recommendation_id": self.recommendation_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
