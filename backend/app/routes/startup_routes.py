import random
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.user import User
from app.models.product import Product
import asyncio
from app.services.realtime_scraper import fetch_multi_platform_prices

startup_bp = Blueprint("startup", __name__)

# In-memory storage for mock integrations configurations
INTEGRATIONS_STORE = {
    "shopify": {
        "connected": True,
        "store_url": "acme-wear.myshopify.com",
        "api_version": "2024-04",
        "last_sync": "2026-07-01T18:30:00Z"
    },
    "woocommerce": {
        "connected": False,
        "store_url": "",
        "api_version": "",
        "last_sync": None
    }
}


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

    # Calculate dynamic mock invoice values based on actual DB product counts
    product_count = Product.query.filter_by(organization_id=current_user.organization_id).count()
    # Assume AI generates an average of ₹1,18,286 (approx $1,420) lift per managed product
    revenue_lift = float(product_count * 1420.00) if product_count > 0 else 45210.00
    
    commission_rate = 0.005 # 0.5%
    commission_charge = round(revenue_lift * commission_rate, 2)
    plan_fee = 149.00 # Pro tier fee
    total_due = round(plan_fee + commission_charge, 2)

    return {
        "success": True,
        "subscription": {
            "tier": "Pro Growth Plan",
            "price_monthly": plan_fee,
            "billing_cycle": "Monthly",
            "next_billing_date": "2026-07-28"
        },
        "usage_metrics": {
            "ai_assisted_revenue_lift": revenue_lift,
            "commission_rate_pct": commission_rate * 100,
            "commission_due": commission_charge,
            "subscription_due": plan_fee,
            "total_invoice_due": total_due
        },
        "billing_history": [
            {"invoice_id": "INV-2026-06", "date": "2026-06-28", "amount": 349.50, "status": "paid"},
            {"invoice_id": "INV-2026-05", "date": "2026-05-28", "amount": 298.12, "status": "paid"},
            {"invoice_id": "INV-2026-04", "date": "2026-04-28", "amount": 149.00, "status": "paid"}
        ]
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
    revenue_lift = float(product_count * 1420.00) if product_count > 0 else 45210.00
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

    if request.method == "POST":
        data = request.get_json() or {}
        platform = data.get("platform")
        connected = bool(data.get("connected", False))
        store_url = data.get("store_url", "")

        if platform not in INTEGRATIONS_STORE:
            return {"success": False, "message": f"Platform '{platform}' is not supported"}, 400

        INTEGRATIONS_STORE[platform]["connected"] = connected
        INTEGRATIONS_STORE[platform]["store_url"] = store_url if connected else ""
        INTEGRATIONS_STORE[platform]["last_sync"] = datetime.now(timezone.utc).isoformat() if connected else None

        return {
            "success": True,
            "message": f"{platform.capitalize()} integration updated successfully",
            "integration": INTEGRATIONS_STORE[platform]
        }, 200

    # GET returns current status and mock webhook logs list
    webhook_logs = [
        {
            "event": "orders/create",
            "topic": "Order Placed",
            "payload_id": "shopify-ord-82918",
            "timestamp": "2026-07-01T19:22:15Z",
            "status": "processed",
            "ai_adjusted": True
        },
        {
            "event": "products/update",
            "topic": "Catalog Sync",
            "payload_id": "shopify-prod-10928",
            "timestamp": "2026-07-01T18:45:00Z",
            "status": "processed",
            "ai_adjusted": False
        },
        {
            "event": "orders/create",
            "topic": "Order Placed",
            "payload_id": "shopify-ord-82909",
            "timestamp": "2026-07-01T17:10:04Z",
            "status": "processed",
            "ai_adjusted": True
        }
    ]

    return {
        "success": True,
        "integrations": INTEGRATIONS_STORE,
        "webhook_logs": webhook_logs
    }, 200
