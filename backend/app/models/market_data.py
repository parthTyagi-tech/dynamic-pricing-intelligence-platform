import uuid
from datetime import datetime, timezone
from app.extensions import db


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


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=False, index=True)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_per_unit = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    product = db.relationship("Product")

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else "Unknown Product",
            "sku": self.product.sku if self.product else "Unknown SKU",
            "quantity": self.quantity,
            "price_per_unit": self.price_per_unit,
            "total_price": round(self.quantity * self.price_per_unit, 2),
            "remaining_inventory": self.product.inventory_quantity if self.product else 0,
            "timestamp": self.timestamp.isoformat()
        }