import uuid

from datetime import datetime, timezone

from app.extensions import db


class ProductCategory:

    ELECTRONICS = "electronics"
    APPAREL = "apparel"
    HOME_GOODS = "home_goods"
    BEAUTY = "beauty"
    SPORTS = "sports"

    ALL = [
        ELECTRONICS,
        APPAREL,
        HOME_GOODS,
        BEAUTY,
        SPORTS
    ]


class RecommendationStatus:

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"

    ALL = [
        PENDING,
        APPROVED,
        REJECTED,
        EXECUTED
    ]


class Product(db.Model):

    __tablename__ = "products"

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    sku = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
        index=True
    )

    name = db.Column(
        db.String(255),
        nullable=False
    )

    category = db.Column(
        db.String(100),
        nullable=False,
        default=ProductCategory.ELECTRONICS
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    current_price = db.Column(
        db.Float,
        nullable=False
    )

    cost_price = db.Column(
        db.Float,
        nullable=False
    )

    inventory_quantity = db.Column(
        db.Integer,
        default=0
    )

    min_margin_percentage = db.Column(
        db.Float,
        default=10.0
    )

    recommendation_status = db.Column(
        db.String(50),
        default=RecommendationStatus.PENDING
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

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # =====================================
    # Relationships
    # =====================================

    organization = db.relationship(
        "Organization",
        back_populates="products"
    )

    recommendations = db.relationship(
        "PricingRecommendation",
        back_populates="product",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    competitor_prices = db.relationship(
        "CompetitorPrice",
        back_populates="product",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    demand_signals = db.relationship(
        "DemandSignal",
        back_populates="product",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    # =====================================
    # Utility Methods
    # =====================================

    def calculate_margin(self):

        if self.current_price <= 0:
            return 0

        return round(
            (
                (
                    self.current_price -
                    self.cost_price
                )
                / self.current_price
            ) * 100,
            2
        )

    def is_low_stock(self):

        return self.inventory_quantity < 10

    def is_overstocked(self):

        return self.inventory_quantity > 100

    def to_dict(self):

        return {
            "id": self.id,
            "sku": self.sku,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "current_price": self.current_price,
            "cost_price": self.cost_price,
            "inventory_quantity": self.inventory_quantity,
            "margin_percentage": self.calculate_margin(),
            "min_margin_percentage": self.min_margin_percentage,
            "recommendation_status": self.recommendation_status,
            "low_stock": self.is_low_stock(),
            "overstocked": self.is_overstocked(),
            "organization_id": self.organization_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }