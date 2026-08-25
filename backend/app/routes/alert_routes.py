from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions import db
from app.models.price_alert import PriceAlert
from app.models.product import Product
from app.models.user import User
from app.services.price_alert_service import acknowledge_alert, detect_and_create_alerts

alert_bp = Blueprint("alerts", __name__)


@alert_bp.get("")
@jwt_required()
def list_alerts():
    user = User.query.get(get_jwt_identity())
    if not user:
        return {"success": False, "message": "User not found"}, 404
    status = request.args.get("status", "open")
    query = PriceAlert.query.filter_by(organization_id=user.organization_id)
    if status != "all":
        query = query.filter_by(status=status)
    alerts = query.order_by(PriceAlert.detected_at.desc()).limit(100).all()
    return {"success": True, "count": len(alerts), "alerts": [alert.to_dict() for alert in alerts]}, 200


@alert_bp.post("/scan")
@jwt_required()
def scan_alerts():
    user = User.query.get(get_jwt_identity())
    if not user:
        return {"success": False, "message": "User not found"}, 404
    payload = request.get_json(silent=True) or {}
    product_id = payload.get("product_id")
    product = Product.query.filter_by(id=product_id, organization_id=user.organization_id).first()
    if not product:
        return {"success": False, "message": "Product not found"}, 404
    observations = payload.get("observations") or {}
    if not isinstance(observations, dict):
        return {"success": False, "message": "observations must be an object keyed by marketplace"}, 400
    previous_prices = payload.get("previous_prices") or {}
    threshold_pct = payload.get("threshold_pct")
    min_drop_inr = payload.get("min_drop_inr")
    alerts = detect_and_create_alerts(product, previous_prices, observations, threshold_pct, min_drop_inr)
    db.session.commit()
    return {"success": True, "count": len(alerts), "alerts": [alert.to_dict() for alert in alerts]}, 200


@alert_bp.patch("/<alert_id>/acknowledge")
@jwt_required()
def acknowledge_alert_route(alert_id):
    user = User.query.get(get_jwt_identity())
    alert = PriceAlert.query.filter_by(id=alert_id, organization_id=user.organization_id if user else None).first()
    if not alert:
        return {"success": False, "message": "Alert not found"}, 404
    acknowledge_alert(alert)
    db.session.commit()
    return {"success": True, "alert": alert.to_dict()}, 200
