import os
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.user import User
from app.models.product import Product
import asyncio
from app.services.realtime_scraper import fetch_multi_platform_prices

startup_bp = Blueprint("startup", __name__)

SUPPORTED_INTEGRATIONS = {"shopify", "woocommerce", "amazon"}

@startup_bp.route("/matcher", methods=["POST"])
@jwt_required()
def competitor_matcher():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    data = request.get_json() or {}
    product_id = data.get("product_id")

    if not product_id:
        return {"success": False, "message": "product_id is required"}, 400

    # Fetch the user's product from database
    product = Product.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()

    if not product:
        return {"success": False, "message": "Product not found in your catalog"}, 404

    # Run multi-platform price intelligence
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    platform_prices = loop.run_until_complete(
        fetch_multi_platform_prices(
            product_name=product.name,
            brand=product.brand or "",
            category=product.category or "",
            baseline_price_usd=product.current_price,
            barcode=product.barcode or "",
            product_id=product.id
        )
    )

    # Convert to ordered list for frontend
    results = []
    for idx, (pname, pdata) in enumerate(platform_prices.items()):
        results.append({
            "id": f"platform-{idx}",
            **pdata
        })

    return {
        "success": True,
        "product": product.to_dict(),
        "platforms": results
    }, 200


@startup_bp.route("/billing", methods=["GET"])
@jwt_required()
def get_billing_summary():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    # Billing data is unavailable until a persisted billing provider is configured.
    product_count = Product.query.filter_by(organization_id=current_user.organization_id).count()
    # Assume AI generates an average of ₹1,18,286 (approx $1,420) lift per managed product
    revenue_lift = 0.0
    
    commission_rate = 0.005 # 0.5%
    commission_charge = round(revenue_lift * commission_rate, 2)
    plan_fee = 149.00 # Pro tier fee
    total_due = round(plan_fee + commission_charge, 2)

    return {
        "success": True,
        "subscription": {
            "tier": None,
            "price_monthly": 0.0,
            "billing_cycle": None,
            "next_billing_date": None
        },
        "usage_metrics": {
            "ai_assisted_revenue_lift": revenue_lift,
            "commission_rate_pct": commission_rate * 100,
            "commission_due": commission_charge,
            "subscription_due": 0.0,
            "total_invoice_due": 0.0
        },
        "billing_history": []
    }, 200


@startup_bp.route("/billing/create-checkout-session", methods=["POST"])
@jwt_required()
def create_checkout_session():
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

    if not stripe.api_key:
        return {"success": False, "message": "STRIPE_SECRET_KEY not configured in backend."}, 500

    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    # Calculate same amount as get_billing_summary
    product_count = Product.query.filter_by(organization_id=current_user.organization_id).count()
    revenue_lift = 0.0
    commission_rate = 0.005
    commission_charge = round(revenue_lift * commission_rate, 2)
    plan_fee = 149.00
    total_due = round(plan_fee + commission_charge, 2)

    try:
        session = stripe.checkout.Session.create(
            line_items=[{
                'price_data': {
                    'currency': 'inr',
                    'product_data': {
                        'name': 'Klypup Pro Growth Plan + AI Commission',
                        'description': f'Usage based dynamic commission on \u20b9{revenue_lift} AI revenue lift',
                    },
                    'unit_amount': int(total_due * 100), # amount in paise
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url="http://localhost:3000/billing?success=true",
            cancel_url="http://localhost:3000/billing?canceled=true",
        )
        return {"success": True, "url": session.url}, 200
    except Exception as e:
        return {"success": False, "message": str(e)}, 500


@startup_bp.route("/integrations", methods=["GET", "POST"])
@jwt_required()
def handle_integrations():
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    if not current_user:
        return {"success": False, "message": "User not found"}, 404

    organization = current_user.organization
    if not organization:
        return {"success": False, "message": "Organization not found"}, 404

    if request.method == "POST":
        data = request.get_json() or {}
        platform = str(data.get("platform", "")).strip().lower()
        connected = bool(data.get("connected", False))
        store_url = str(data.get("store_url", "")).strip()
        if platform not in SUPPORTED_INTEGRATIONS:
            return {"success": False, "message": f"Platform '{platform}' is not supported"}, 400
        if connected and not store_url:
            return {"success": False, "message": "store_url is required when connecting an integration"}, 400
        organization.store_platform = platform if connected else None
        organization.store_domain = store_url if connected else None
        db.session.commit()

    current_platform = organization.store_platform
    current_domain = organization.store_domain
    integrations = {
        platform: {
            "connected": platform == current_platform and bool(current_domain),
            "store_url": current_domain if platform == current_platform else "",
            "api_version": "",
            "last_sync": None,
        }
        for platform in sorted(SUPPORTED_INTEGRATIONS)
    }
    return {"success": True, "integrations": integrations, "webhook_logs": []}, 200
