import random
import uuid
from datetime import datetime, timedelta, timezone
from flask import Flask
from app.config.settings import get_config
from app.extensions import db
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.models.product import Product, ProductCategory, RecommendationStatus
from app.models.recommendation import PricingRecommendation, ApprovalAction, ApprovalActionType
from app.models.market_data import CompetitorPrice, DemandSignal
from app.models.audit_loging import PricingRule, AuditLog
from app.models.ab_test import ABTest

def create_seed_app():
    app = Flask(__name__)
    app.config.from_object(get_config())
    db.init_app(app)
    return app

def seed_database():
    app = create_seed_app()
    with app.app_context():
        print("Recreating database tables...")
        db.drop_all()
        db.create_all()

        print("Creating seed organization...")
        org = Organization(
            name="Acme Pricing Corp",
            invite_code="ACME1234"
        )
        db.session.add(org)
        db.session.flush()

        print("Creating seed users...")
        admin = User(
            name="Admin User",
            email="admin@acme.com",
            role=UserRole.ADMIN,
            organization_id=org.id
        )
        admin.set_password("password")

        analyst = User(
            name="Analyst User",
            email="analyst@acme.com",
            role=UserRole.ANALYST,
            organization_id=org.id
        )
        analyst.set_password("password")

        db.session.add(admin)
        db.session.add(analyst)
        db.session.flush()

        print("Creating organization pricing rules...")
        rule = PricingRule(
            auto_execute_threshold=0.90,
            minimum_margin=0.15,
            organization_id=org.id
        )
        db.session.add(rule)

        print("Seeding product catalog...")
        seed_products = [
            # Electronics
            {"name": "Premium Wireless Headphones", "category": ProductCategory.ELECTRONICS, "desc": "Active noise cancelling bluetooth headphones", "price": 199.99, "cost": 110.00, "inventory": 45},
            {"name": "Mechanical Gaming Keyboard", "category": ProductCategory.ELECTRONICS, "desc": "RGB backlit tactile mechanical keyboard", "price": 129.99, "cost": 65.00, "inventory": 9},
            {"name": "Ultra HD Projector 4K", "category": ProductCategory.ELECTRONICS, "desc": "High brightness home theater projector", "price": 799.99, "cost": 450.00, "inventory": 5},
            {"name": "Smart Watch Series X", "category": ProductCategory.ELECTRONICS, "desc": "Fitness tracker with heart rate monitor", "price": 249.99, "cost": 140.00, "inventory": 28},
            # Apparel
            {"name": "Running Sneakers Zoom", "category": ProductCategory.APPAREL, "desc": "Lightweight breathable mesh running shoes", "price": 89.99, "cost": 40.00, "inventory": 110},
            {"name": "Waterproof Windbreaker Jacket", "category": ProductCategory.APPAREL, "desc": "All-weather outdoor shell jacket", "price": 119.99, "cost": 55.00, "inventory": 15},
            {"name": "Classic Denim Jeans", "category": ProductCategory.APPAREL, "desc": "Straight fit stretch raw denim jeans", "price": 59.99, "cost": 22.00, "inventory": 75},
            # Home Goods
            {"name": "Ergonomic Office Chair", "category": ProductCategory.HOME_GOODS, "desc": "Mesh high-back executive task chair", "price": 349.99, "cost": 180.00, "inventory": 12},
            {"name": "Cold Brew Coffee Maker", "category": ProductCategory.HOME_GOODS, "desc": "Glass carafe pitcher with stainless filter", "price": 39.99, "cost": 15.00, "inventory": 60},
            {"name": "Dimmable LED Desk Lamp", "category": ProductCategory.HOME_GOODS, "desc": "Smart desk light with USB charging port", "price": 29.99, "cost": 10.50, "inventory": 40},
            # Beauty
            {"name": "Hydrating Face Serum", "category": ProductCategory.BEAUTY, "desc": "Pure hyaluronic acid moisture booster", "price": 35.00, "cost": 12.00, "inventory": 200},
            {"name": "Mineral Sunscreen SPF 50", "category": ProductCategory.BEAUTY, "desc": "Broad spectrum non-greasy face sunscreen", "price": 22.50, "cost": 8.00, "inventory": 95},
            # Sports
            {"name": "Resistance Bands Set", "category": ProductCategory.SPORTS, "desc": "Heavy duty loop fitness workout bands", "price": 24.99, "cost": 8.50, "inventory": 15},
            {"name": "Premium Yoga Mat", "category": ProductCategory.SPORTS, "desc": "Extra thick non-slip eco friendly exercise mat", "price": 45.00, "cost": 18.00, "inventory": 32},
        ]

        products_db = []
        for idx, sp in enumerate(seed_products):
            p = Product(
                sku=f"SKU-{sp['category'].upper()[:3]}-{idx:03d}",
                name=sp['name'],
                category=sp['category'],
                description=sp['desc'],
                current_price=sp['price'],
                cost_price=sp['cost'],
                inventory_quantity=sp['inventory'],
                min_margin_percentage=15.0,
                organization_id=org.id,
                recommendation_status=RecommendationStatus.PENDING if idx % 2 == 0 else RecommendationStatus.APPROVED
            )
            db.session.add(p)
            products_db.append(p)
        db.session.flush()

        print("Seeding competitor prices and demand signals...")
        competitors = ["Amazon", "Walmart", "BestBuy", "Target", "Ebay"]
        for p in products_db:
            # Seed competitor prices
            num_competitors = random.randint(2, 4)
            chosen_competitors = random.sample(competitors, num_competitors)
            for comp_name in chosen_competitors:
                comp_price_val = round(p.current_price * random.uniform(0.90, 1.10), 2)
                cp = CompetitorPrice(
                    competitor_name=comp_name,
                    competitor_price=comp_price_val,
                    product_id=p.id,
                    organization_id=org.id,
                    checked_at=datetime.now(timezone.utc) - timedelta(hours=random.randint(1, 24))
                )
                db.session.add(cp)

            # Seed demand signals
            for i in range(2):
                ds = DemandSignal(
                    trend_score=random.uniform(0.45, 0.95),
                    seasonal_factor=random.uniform(0.9, 1.2),
                    sku_velocity=random.uniform(5.0, 50.0),
                    product_id=p.id,
                    organization_id=org.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=i)
                )
                db.session.add(ds)
        db.session.flush()

        print("Seeding pricing recommendations and audit log history...")
        # Create some pending, approved, and rejected recommendations
        for i, p in enumerate(products_db):
            # Rec 1: Pending
            if i % 3 == 0:
                rec = PricingRecommendation(
                    product_id=p.id,
                    recommended_price=round(p.current_price * random.choice([0.92, 0.95, 1.05, 1.08]), 2),
                    confidence_score=random.uniform(0.65, 0.98),
                    rationale=f"Recommended price update for {p.name} driven by inventory level ({p.inventory_quantity} units) and high category demand signals.",
                    status=RecommendationStatus.PENDING,
                    ai_summary="Optimized margins based on stock level pressure.",
                    created_by_agent="PricingStrategyAgent",
                    agent_analysis={
                        "market_agent": {"avg_competitor_price": round(p.current_price * 0.98, 2), "price_gap_pct": 2.0},
                        "demand_agent": {"demand_score": 85, "trend": "rising"},
                        "inventory_agent": {"inventory_level": p.inventory_quantity, "stock_status": "healthy"}
                    },
                    organization_id=org.id,
                    created_at=datetime.now(timezone.utc) - timedelta(hours=3)
                )
                db.session.add(rec)
                p.recommendation_status = RecommendationStatus.PENDING

            # Rec 2: Approved historically
            elif i % 3 == 1:
                prev_price = round(p.current_price * 0.90, 2)
                rec = PricingRecommendation(
                    product_id=p.id,
                    recommended_price=p.current_price, # Current price matches approved suggested price
                    confidence_score=random.uniform(0.70, 0.99),
                    rationale=f"Approved premium adjustment for {p.name}. Market analysis indicated standard competitor pricing premium was achievable.",
                    status=RecommendationStatus.APPROVED,
                    ai_summary="Approved upward premium pricing adjustment.",
                    created_by_agent="PricingStrategyAgent",
                    agent_analysis={
                        "market_agent": {"avg_competitor_price": round(p.current_price * 0.95, 2), "price_gap_pct": 5.0},
                        "demand_agent": {"demand_score": 90, "trend": "rising"},
                        "inventory_agent": {"inventory_level": p.inventory_quantity, "stock_status": "low_stock"}
                    },
                    organization_id=org.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=2)
                )
                db.session.add(rec)
                db.session.flush()

                action = ApprovalAction(
                    recommendation_id=rec.id,
                    action_type=ApprovalActionType.APPROVE,
                    previous_price=prev_price,
                    executed_price=p.current_price,
                    approved_by=admin.id,
                    timestamp=datetime.now(timezone.utc) - timedelta(days=2, hours=1)
                )
                db.session.add(action)
                p.recommendation_status = RecommendationStatus.APPROVED

            # Rec 3: Rejected historically
            else:
                suggested = round(p.current_price * 1.25, 2)
                rec = PricingRecommendation(
                    product_id=p.id,
                    recommended_price=suggested,
                    confidence_score=random.uniform(0.50, 0.75),
                    rationale=f"Suggested increase of 25% due to seasonal surge prediction.",
                    status=RecommendationStatus.REJECTED,
                    ai_summary="Aggressive premium increase recommendation.",
                    created_by_agent="PricingStrategyAgent",
                    agent_analysis={
                        "market_agent": {"avg_competitor_price": p.current_price, "price_gap_pct": 0.0},
                        "demand_agent": {"demand_score": 60, "trend": "stable"},
                        "inventory_agent": {"inventory_level": p.inventory_quantity, "stock_status": "healthy"}
                    },
                    organization_id=org.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=4)
                )
                db.session.add(rec)
                db.session.flush()

                action = ApprovalAction(
                    recommendation_id=rec.id,
                    action_type=ApprovalActionType.REJECT,
                    previous_price=p.current_price,
                    executed_price=suggested,
                    approved_by=analyst.id,
                    rejection_reason="Proposed price increase of 25% exceeds the 10% maximum price step constraint for this season.",
                    timestamp=datetime.now(timezone.utc) - timedelta(days=3, hours=5)
                )
                db.session.add(action)
                p.recommendation_status = RecommendationStatus.REJECTED

        db.session.commit()
        print("\n" + "="*50)
        print("SEEDING COMPLETED SUCCESSFULLY!")
        print("="*50)
        print(f"Organization Invite Code: {org.invite_code}")
        print("Seeded User Accounts:")
        print(f"  - Admin:   email: admin@acme.com   password: password")
        print(f"  - Analyst: email: analyst@acme.com password: password")
        print(f"Seeded Products:   {len(products_db)}")
        print(f"Seeded competitor price checks & demand signals.")
        print("="*50 + "\n")

if __name__ == "__main__":
    seed_database()
