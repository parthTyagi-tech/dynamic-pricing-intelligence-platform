import uuid
from datetime import datetime, timezone
from app.extensions import db

class ABTest(db.Model):
    __tablename__ = "ab_tests"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = db.Column(db.String(36), db.ForeignKey("products.id"), nullable=False, index=True)
    organization_id = db.Column(db.String(36), db.ForeignKey("organizations.id"), nullable=False, index=True)
    
    price_a = db.Column(db.Float, nullable=False)
    price_b = db.Column(db.Float, nullable=False)
    
    # Track simulated or actual sales volume/revenue during the test
    sales_a = db.Column(db.Integer, default=0)
    sales_b = db.Column(db.Integer, default=0)
    revenue_a = db.Column(db.Float, default=0.0)
    revenue_b = db.Column(db.Float, default=0.0)
    
    status = db.Column(db.String(32), default="active") # active, completed
    winner = db.Column(db.String(32), nullable=True) # A, B
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    product = db.relationship("Product", backref="ab_tests")
    organization = db.relationship("Organization")

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "price_a": self.price_a,
            "price_b": self.price_b,
            "sales_a": self.sales_a,
            "sales_b": self.sales_b,
            "revenue_a": self.revenue_a,
            "revenue_b": self.revenue_b,
            "status": self.status,
            "winner": self.winner,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
