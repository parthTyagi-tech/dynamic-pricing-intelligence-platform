from flask import Blueprint, request, current_app
from flask_jwt_extended import create_access_token
import os
import uuid
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from app.extensions import db
from app.models.user import User
from app.models.product import Product
from app.models.organization import Organization
from app.services.email_service import send_login_email, send_password_reset_email
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


# =====================================
# FORGOT PASSWORD ROUTE
# =====================================
@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()

    if not email:
        return {"success": False, "message": "Email address is required"}, 400

    user = User.query.filter_by(email=email).first()
    if user:
        try:
            secret = current_app.config.get("SECRET_KEY", "klypup_super_secret_flask_key")
        except Exception:
            secret = os.environ.get("SECRET_KEY", "klypup_super_secret_flask_key")

        serializer = URLSafeTimedSerializer(secret)
        token = serializer.dumps({"user_id": user.id, "email": user.email}, salt="password-reset")

        # Determine frontend origin for the link
        origin = request.headers.get("Origin") or request.headers.get("Referer")
        if origin:
            frontend_url = origin.rstrip("/")
            if "/login" in frontend_url or "/signup" in frontend_url or "/forgot-password" in frontend_url:
                frontend_url = frontend_url.split("/login")[0].split("/signup")[0].split("/forgot-password")[0].rstrip("/")
        else:
            is_local = "localhost" in request.host or "127.0.0.1" in request.host
            frontend_url = "http://localhost:5173" if is_local else "https://dynamic-pricing-intelligence-platfo.vercel.app"

        reset_url = f"{frontend_url}/reset-password?token={token}"

        try:
            import threading
            threading.Thread(
                target=send_password_reset_email,
                args=(user.email, user.name, reset_url),
                daemon=True
            ).start()
        except Exception as e:
            print(f"[Auth Route] Failed to trigger background password reset email: {e}")

    # Return standard generic message to prevent email enumeration
    return {
        "success": True,
        "message": "If an account exists with that email, password reset instructions have been sent to your inbox."
    }, 200


# =====================================
# RESET PASSWORD ROUTE
# =====================================
@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json(silent=True) or {}
    token = str(data.get("token", "")).strip()
    new_password = str(data.get("new_password") or data.get("password") or "").strip()

    if not token:
        return {"success": False, "message": "Reset token is required"}, 400

    if not new_password or len(new_password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters long"}, 400

    try:
        secret = current_app.config.get("SECRET_KEY", "klypup_super_secret_flask_key")
    except Exception:
        secret = os.environ.get("SECRET_KEY", "klypup_super_secret_flask_key")

    serializer = URLSafeTimedSerializer(secret)
    try:
        payload = serializer.loads(token, salt="password-reset", max_age=3600)
    except SignatureExpired:
        return {"success": False, "message": "The reset link has expired. Please request a new one."}, 400
    except BadSignature:
        return {"success": False, "message": "The reset link is invalid or corrupted. Please request a new one."}, 400

    user_id = payload.get("user_id")
    user = User.query.get(user_id)
    if not user:
        return {"success": False, "message": "User account no longer exists"}, 404

    user.set_password(new_password)
    db.session.commit()

    return {
        "success": True,
        "message": "Your password has been successfully reset. Please log in with your new password."
    }, 200


# =====================================
# GOOGLE OAUTH SIGN-IN / SIGN-UP
# =====================================
@auth_bp.route("/google", methods=["POST"])
@auth_bp.route("/google-login", methods=["POST"])
def google_auth():
    data = request.get_json(silent=True) or {}
    token = data.get("credential") or data.get("id_token") or data.get("token")
    code = data.get("code")
    redirect_uri = data.get("redirect_uri") or "http://localhost:5173"

    client_id = (
        current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")
        or os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    ).strip()
    client_secret = (
        current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET")
        or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
    ).strip()

    # If an authorization code was provided, exchange it for tokens
    if code and not token:
        try:
            import requests as py_requests
            token_resp = py_requests.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=10,
            )
            if token_resp.status_code == 200:
                token_data = token_resp.json()
                token = token_data.get("id_token") or token_data.get("access_token")
            else:
                return {
                    "success": False,
                    "message": f"Failed to exchange Google authorization code: {token_resp.text}",
                }, 400
        except Exception as e:
            return {"success": False, "message": f"Google code exchange failed: {e}"}, 400

    if not token:
        return {"success": False, "message": "Google credential token or code is required"}, 400

    google_data = None

    # Step 1: Cryptographic ID token verification via google.oauth2.id_token
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests

        google_data = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            client_id if client_id else None
        )
    except Exception as e:
        print(f"[Google Auth] verify_oauth2_token failed, trying tokeninfo endpoint: {e}")

    # Step 2: Fallback to Google's official tokeninfo and userinfo endpoints
    if not google_data:
        try:
            import requests as py_requests
            # Check if token is an id_token
            resp = py_requests.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={token}",
                timeout=8
            )
            if resp.status_code == 200:
                google_data = resp.json()
            else:
                # Check if token is an access_token
                acc_resp = py_requests.get(
                    f"https://oauth2.googleapis.com/tokeninfo?access_token={token}",
                    timeout=8
                )
                if acc_resp.status_code == 200:
                    google_data = acc_resp.json()

                # Also retrieve user profile information via userinfo
                userinfo_resp = py_requests.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=8
                )
                if userinfo_resp.status_code == 200:
                    u_info = userinfo_resp.json()
                    if google_data:
                        google_data.update(u_info)
                    else:
                        google_data = u_info
        except Exception as e:
            print(f"[Google Auth] tokeninfo/userinfo request failed: {e}")

    if not google_data:
        return {"success": False, "message": "Invalid or expired Google token"}, 401

    # Verify audience when client_id is set and aud is in payload
    aud = google_data.get("aud") or google_data.get("audience")
    if client_id and aud and aud != client_id:
        return {"success": False, "message": "Token was not issued for this application"}, 401

    google_email = google_data.get("email")
    if not google_email:
        return {"success": False, "message": "Google account does not provide an email address"}, 400

    google_sub = google_data.get("sub")
    google_name = google_data.get("name") or google_email.split("@")[0]

    # Find existing user by oauth_id or email
    user = User.query.filter_by(oauth_provider="google", oauth_id=google_sub).first()
    if not user:
        user = User.query.filter_by(email=google_email).first()
        if user:
            user.oauth_provider = "google"
            user.oauth_id = google_sub
            db.session.commit()

    if not user:
        # Create organization for new user
        org_name = f"{google_name}'s Workspace"
        org = Organization(
            name=org_name,
            invite_code=str(uuid.uuid4())[:8]
        )
        db.session.add(org)
        db.session.flush()

        user = User(
            name=google_name,
            email=google_email,
            role="admin",
            organization_id=org.id,
            oauth_provider="google",
            oauth_id=google_sub
        )
        db.session.add(user)
        db.session.commit()

    # Generate JWT token
    jwt_token = create_access_token(identity=user.id)

    # Optional background login alert email
    try:
        import threading
        threading.Thread(
            target=send_login_email,
            args=(user.email, user.name, request.remote_addr or "unknown", request.headers.get("User-Agent", "unknown"), "google_oauth", "GOOGLE SIGN IN"),
            daemon=True
        ).start()
    except Exception as e:
        print(f"[Google Auth] Background email dispatch failed: {e}")

    return {
        "success": True,
        "message": f"Welcome back, {user.name}!",
        "token": jwt_token,
        "user": user.to_dict()
    }, 200

