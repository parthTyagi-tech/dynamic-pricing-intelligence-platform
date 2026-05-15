import uuid
from datetime import datetime, timezone
from app.extensions import db


class CompetitorPrice(db.Model):
    __tablename__ = "competitor_prices"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    competitor_name = db.Column(db.String(255), nullable=False)
    competitor_price = db.Column(db.Float, nullable=False)
    product_id = db.Column(
        db.String(36), db.ForeignKey("products.id"), nullable=False, index=True
    )
    organization_id = db.Column(
        db.String(36), db.ForeignKey("organizations.id"), nullable=False, index=True
    )
    checked_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    product = db.relationship("Product", back_populates="competitor_prices")

    def to_dict(self):
        return {
            "id": self.id,
            "competitor_name": self.competitor_name,
            "competitor_price": self.competitor_price,
            "product_id": self.product_id,
            "organization_id": self.organization_id,
            "checked_at": self.checked_at.isoformat(),
        }


class DemandSignal(db.Model):
    __tablename__ = "demand_signals"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trend_score = db.Column(db.Float, nullable=False, default=0.5)
    seasonal_factor = db.Column(db.Float, nullable=False, default=1.0)
    sku_velocity = db.Column(db.Float, nullable=False, default=0.0)
    product_id = db.Column(
        db.String(36), db.ForeignKey("products.id"), nullable=False, index=True
    )
    organization_id = db.Column(
        db.String(36), db.ForeignKey("organizations.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    product = db.relationship("Product", back_populates="demand_signals")

    def to_dict(self):
        return {
            "id": self.id,
            "trend_score": self.trend_score,
            "seasonal_factor": self.seasonal_factor,
            "sku_velocity": self.sku_velocity,
            "product_id": self.product_id,
            "organization_id": self.organization_id,
            "created_at": self.created_at.isoformat(),
        }