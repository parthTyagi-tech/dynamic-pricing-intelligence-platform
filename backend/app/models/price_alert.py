import uuid
from datetime import datetime, timezone

from app.extensions import db


class PriceAlert(db.Model):
    __tablename__ = "price_alerts"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False, index=True)
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=False, index=True)
    competitor_name = db.Column(db.String(255), nullable=False, index=True)
    previous_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float, nullable=False)
    drop_percent = db.Column(db.Float, nullable=False)
    drop_amount = db.Column(db.Float, nullable=False)
    threshold_percent = db.Column(db.Float, nullable=False, default=5.0)
    status = db.Column(db.String(24), nullable=False, default="open", index=True)
    detected_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)

    product = db.relationship("Product")

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else "Unknown product",
            "sku": self.product.sku if self.product else "Unknown SKU",
            "competitor_name": self.competitor_name,
            "previous_price": round(self.previous_price, 2),
            "current_price": round(self.current_price, 2),
            "drop_percent": round(self.drop_percent, 2),
            "drop_amount": round(self.drop_amount, 2),
            "threshold_percent": round(self.threshold_percent, 2),
            "status": self.status,
            "detected_at": self.detected_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
        }
