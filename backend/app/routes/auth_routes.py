from flask import Blueprint, request
from flask_jwt_extended import create_access_token

import uuid

from app.extensions import db
from app.models.user import User
from app.models.organization import Organization

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
        role="admin",
        organization_id=organization.id
    )

    # Hash password
    user.set_password(
        data["password"]
    )

    db.session.add(user)

    db.session.commit()

    return {
        "success": True,
        "message": "User registered successfully",
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
    token = create_access_token(
        identity=user.id
    )

    return {
        "success": True,
        "message": "Login successful",
        "token": token,
        "user": user.to_dict()
    }, 200