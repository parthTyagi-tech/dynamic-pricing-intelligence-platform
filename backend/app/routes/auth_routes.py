from flask import Blueprint, request
from flask_jwt_extended import create_access_token

import uuid

from app.extensions import db
from app.models.user import User
from app.models.product import Product
from app.models.organization import Organization
from app.services.email_service import send_login_email
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
@auth_bp.route(
    "/signup",
    methods=["POST"]
)
def register():

    # Get JSON data
    data = request.get_json(silent=True) or {}

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

    # Send registration security email in background through Brevo.
    try:
        import threading
        threading.Thread(
            target=send_login_email,
            args=(user.email, user.name, request.remote_addr or "unknown", request.headers.get("User-Agent", "unknown"), "registration", "REGISTRATION"),
            daemon=True
        ).start()
    except Exception as e:
        print(f"[Auth Route] Failed to trigger background registration email: {e}")

    # Send WhatsApp welcome message if phone number provided in background
    if user.phone_number:
        try:
            import threading
            threading.Thread(
                target=send_whatsapp_welcome,
                args=(user.phone_number, user.name),
                daemon=True
            ).start()
        except Exception as e:
            print(f"[Auth Route] Failed to trigger background WhatsApp welcome: {e}")

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

    data = request.get_json(silent=True) or {}
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
        import threading
        threading.Thread(
            target=send_login_email,
            args=(user.email, user.name, request.remote_addr or "unknown", request.headers.get("User-Agent", "unknown"), access_token[-12:], "LOGIN"),
            daemon=True
        ).start()
    except Exception as e:
        print(f"[Auth Route] Failed to trigger background login email: {e}")

    if user.phone_number:
        try:
            from app.services.whatsapp_service import send_whatsapp_welcome
            import threading
            threading.Thread(
                target=send_whatsapp_welcome,
                args=(user.phone_number, user.name),
                daemon=True
            ).start()
        except Exception as e:
            print(f"[Auth Route] Failed to trigger background login WhatsApp: {e}")

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
# CONNECT STORE INTEGRATION
# =====================================
@auth_bp.route("/connect-integration", methods=["POST"])
@jwt_required()
def connect_integration():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return {"success": False, "message": "User not found"}, 404

    org = user.organization
    if not org:
        return {"success": False, "message": "Organization not found"}, 404

    data = request.get_json() or {}
    platform = str(data.get("platform", "")).strip().lower()
    domain = str(data.get("domain", "")).strip()
    if platform not in {"shopify", "woocommerce", "amazon"}:
        return {"success": False, "message": "Supported platforms are shopify, woocommerce, and amazon"}, 400
    if not domain or len(domain) > 255 or any(char.isspace() for char in domain):
        return {"success": False, "message": "A valid store domain is required"}, 400

    # Store metadata is persisted for the authenticated organization. Catalog data
    # must come from the CSV importer or a verified provider adapter; this route
    # intentionally never invents products, prices, demand, or competitor records.
    org.store_platform = platform
    org.store_domain = domain
    db.session.commit()

    return {
        "success": True,
        "message": f"{platform.capitalize()} connection saved. Import or sync the verified catalog to continue.",
        "user": user.to_dict(),
        "catalog_count": Product.query.filter_by(organization_id=org.id).count(),
    }, 200
