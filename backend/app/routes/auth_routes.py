from flask import Blueprint, request
from flask_jwt_extended import create_access_token

import uuid

from app.extensions import db
from app.models.user import User
from app.models.organization import Organization
from app.services.email_service import send_registration_email
from app.services.whatsapp_service import send_whatsapp_welcome

from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity
)
# Create blueprint
auth_bp = Blueprint(
    "auth",
    __name__
)


# =========================
# REGISTER ROUTE
# =========================
@auth_bp.route(
    "/register",
    methods=["POST"]
)
def register():

    # Get JSON data
    data = request.get_json()

    # Validate required fields
    required_fields = [
        "name",
        "email",
        "password"
    ]

    for field in required_fields:

        if field not in data:

            return {
                "success": False,
                "message": f"{field} is required"
            }, 400

    # Check if email already exists
    existing_user = User.query.filter_by(
        email=data["email"]
    ).first()

    if existing_user:

        return {
            "success": False,
            "message": "Email already exists"
        }, 400

    # Create organization
    organization = Organization(
        name=data.get(
            "organization_name",
            "Default Organization"
        ),
        invite_code=str(uuid.uuid4())[:8]
    )

    db.session.add(organization)

    # Flush to generate organization ID
    db.session.flush()

    # Create user
    user = User(
        name=data["name"],
        email=data["email"],
        phone_number=data.get("phone_number"),
        role="admin",
        organization_id=organization.id
    )

    # Hash password
    user.set_password(
        data["password"]
    )

    db.session.add(user)

    db.session.commit()

    # Send welcoming onboarding email
    try:
        send_registration_email(user.email, user.name)
    except Exception as e:
        print(f"[Auth Route] Failed to send registration email: {e}")

    # Send WhatsApp welcome message if phone number provided
    if user.phone_number:
        try:
            send_whatsapp_welcome(user.phone_number, user.name)
        except Exception as e:
            print(f"[Auth Route] Failed to send WhatsApp welcome: {e}")

    # Generate JWT token
    token = create_access_token(
        identity=user.id
    )

    return {
        "success": True,
        "message": "User registered successfully",
        "token": token,
        "user": user.to_dict()
    }, 201


# =========================
# LOGIN ROUTE
# =========================
# =========================
# PROFILE ROUTE
# =========================
@auth_bp.route(
    "/profile",
    methods=["GET"]
)
@jwt_required()
def profile():

    current_user_id = get_jwt_identity()

    user = User.query.get(
        current_user_id
    )

    if not user:

        return {
            "success": False,
            "message": "User not found"
        }, 404

    return {
        "success": True,
        "user": user.to_dict()
    }, 200
@auth_bp.route(
    "/login",
    methods=["POST"]
)
def login():

    data = request.get_json()

    # Validate fields
    required_fields = [
        "email",
        "password"
    ]

    for field in required_fields:

        if field not in data:

            return {
                "success": False,
                "message": f"{field} is required"
            }, 400

    # Find user
    user = User.query.filter_by(
        email=data["email"]
    ).first()

    # Check user exists
    if not user:

        return {
            "success": False,
            "message": "User not found"
        }, 404

    # Verify password
    if not user.check_password(
        data["password"]
    ):

        return {
            "success": False,
            "message": "Invalid credentials"
        }, 401

    # Generate JWT token
    access_token = create_access_token(
        identity=user.id
    )

    try:
        from app.services.email_service import send_registration_email
        # Repurpose the registration email as a welcome/login email for now, 
        # since the user explicitly requested an email upon login.
        send_registration_email(user.email, user.name)
    except Exception as e:
        print(f"[Auth Route] Failed to send login email: {e}")

    if user.phone_number:
        try:
            from app.services.whatsapp_service import send_whatsapp_welcome
            send_whatsapp_welcome(user.phone_number, user.name)
        except Exception as e:
            print(f"[Auth Route] Failed to send login WhatsApp: {e}")

    return {
        "success": True,
        "message": "Login successful",
        "token": access_token,
        "user": user.to_dict()
    }, 200

# =========================
# COMPLETE ONBOARDING ROUTE
# =========================
@auth_bp.route(
    "/complete-onboarding",
    methods=["POST"]
)
@jwt_required()
def complete_onboarding():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        return {
            "success": False,
            "message": "User not found"
        }, 404

    org = user.organization
    if not org:
        return {
            "success": False,
            "message": "Organization not found"
        }, 404

    org.onboarding_completed = True
    db.session.commit()

    return {
        "success": True,
        "message": "Onboarding completed successfully",
        "user": user.to_dict()
    }, 200

# =====================================
# CONNECT STORE INTEGRATION & SEED CATALOG
# =====================================
@auth_bp.route(
    "/connect-integration",
    methods=["POST"]
)
@jwt_required()
def connect_integration():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if not user:
        return {
            "success": False,
            "message": "User not found"
        }, 404

    org = user.organization
    if not org:
        return {
            "success": False,
            "message": "Organization not found"
        }, 404

    data = request.get_json() or {}
    platform = data.get("platform")
    domain = data.get("domain")

    if not platform:
        return {
            "success": False,
            "message": "Platform identifier is required"
        }, 400

    # Save to organization
    org.store_platform = platform.lower()
    org.store_domain = domain or f"{platform.lower()}-store-{org.id[:6]}"
    
    # Seed Products & Competitor Price Matrices
    from app.models.product import Product
    from app.models.market_data import CompetitorPrice, DemandSignal
    from datetime import datetime, timezone, timedelta

    # Delete any existing products for this org to prevent clutter during testing
    Product.query.filter_by(organization_id=org.id).delete()
    
    products_to_seed = []
    if platform.lower() == "shopify":
        products_to_seed = [
            {"sku": "SKU-SHPF-001", "name": "Shopify Tech Zip Hoodie", "category": "Apparel", "current_price": 65.00, "cost_price": 20.00, "inventory_quantity": 120, "description": "Premium dual-knit Shopify logo hoodie."},
            {"sku": "SKU-SHPF-002", "name": "Shopify Ergonomic Mousepad", "category": "Accessories", "current_price": 25.00, "cost_price": 8.00, "inventory_quantity": 300, "description": "Memory foam wrist-rest desk mat."},
            {"sku": "SKU-SHPF-003", "name": "Shopify Ceramic Travel Mug", "category": "Accessories", "current_price": 18.50, "cost_price": 5.00, "inventory_quantity": 450, "description": "Double-walled travel mug for hot beverages."},
            {"sku": "SKU-SHPF-004", "name": "Shopify Pro Snapback Hat", "category": "Apparel", "current_price": 30.00, "cost_price": 10.00, "inventory_quantity": 180, "description": "Structured flat brim snapback cap."}
        ]
    elif platform.lower() == "walmart":
        products_to_seed = [
            {"sku": "SKU-WMRT-001", "name": "Walmart Great Value Pack", "category": "Groceries", "current_price": 12.99, "cost_price": 4.00, "inventory_quantity": 800, "description": "Premium bulk pantry staples variety bundle."},
            {"sku": "SKU-WMRT-002", "name": "Walmart Equate Daily Care Kit", "category": "Accessories", "current_price": 15.50, "cost_price": 6.00, "inventory_quantity": 600, "description": "Daily hygiene and essential wellness kit."},
            {"sku": "SKU-WMRT-003", "name": "Walmart Mainstays Bed Pillow", "category": "General", "current_price": 19.99, "cost_price": 7.50, "inventory_quantity": 400, "description": "Hypoallergenic supportive microfiber bed pillow."},
            {"sku": "SKU-WMRT-004", "name": "Walmart Athletic crew socks", "category": "Apparel", "current_price": 9.99, "cost_price": 3.00, "inventory_quantity": 1000, "description": "Pack of 6 cushioned running socks."}
        ]
    else:
        products_to_seed = [
            {"sku": "SKU-GLB-001", "name": f"{platform.capitalize()} Pro Wireless Headphones", "category": "Electronics", "current_price": 120.00, "cost_price": 45.00, "inventory_quantity": 100, "description": "Active noise-cancelling over-ear headphones."},
            {"sku": "SKU-GLB-002", "name": f"{platform.capitalize()} Fast Wireless Charger", "category": "Electronics", "current_price": 35.00, "cost_price": 12.00, "inventory_quantity": 250, "description": "Qi-certified 15W rapid wireless charging pad."},
            {"sku": "SKU-GLB-003", "name": f"{platform.capitalize()} Stainless Steel Flask", "category": "Fitness", "current_price": 25.00, "cost_price": 7.00, "inventory_quantity": 500, "description": "Double-walled vacuum insulated flask."},
            {"sku": "SKU-GLB-004", "name": f"{platform.capitalize()} Sleep Orthopedic Pillow", "category": "General", "current_price": 45.00, "cost_price": 15.00, "inventory_quantity": 150, "description": "Contour memory foam sleep support pillow."}
        ]

    now = datetime.now(timezone.utc)
    
    for item in products_to_seed:
        prod = Product(
            sku=item["sku"],
            name=item["name"],
            category=item["category"],
            current_price=item["current_price"],
            cost_price=item["cost_price"],
            inventory_quantity=item["inventory_quantity"],
            description=item["description"],
            organization_id=org.id
        )
        db.session.add(prod)
        db.session.flush()

        # Add competitor price records
        competitors = [
            ("Amazon", 0.96),
            ("Flipkart", 1.02),
            ("Walmart" if platform.lower() != "walmart" else "Target", 0.98)
        ]
        for comp_name, variance in competitors:
            cp = CompetitorPrice(
                competitor_name=comp_name,
                competitor_price=round(prod.current_price * variance, 2),
                product_id=prod.id,
                organization_id=org.id,
                checked_at=now - timedelta(hours=2)
            )
            db.session.add(cp)

        # Add initial demand signals
        ds = DemandSignal(
            trend_score=0.75,
            seasonal_factor=1.05,
            sku_velocity=15.0,
            product_id=prod.id,
            organization_id=org.id,
            created_at=now - timedelta(hours=1)
        )
        db.session.add(ds)

    db.session.commit()

    return {
        "success": True,
        "message": f"Successfully connected to {platform} and seeded store catalog.",
        "user": user.to_dict()
    }, 200