import logging
from flask import Blueprint, request, current_app
from app.extensions import db
from app.models.product import Product
from app.models.market_data import DemandSignal, Sale

logger = logging.getLogger(__name__)

webhook_bp = Blueprint("webhooks", __name__)

@webhook_bp.route("/shopify/order", methods=["POST"])
def shopify_order_webhook():
    """
    Simulates a Shopify order creation webhook.
    Extracts SKUs from the order and increments their sales velocity to signal demand.
    """
    data = request.get_json() or {}
    line_items = data.get("line_items", [])
    
    if not line_items:
        return {"success": False, "message": "No line items in order payload"}, 400

    processed_skus = []

    for item in line_items:
        sku = item.get("sku")
        quantity = item.get("quantity", 1)
        
        if not sku:
            continue
            
        product = Product.query.filter_by(sku=sku).first()
        if not product:
            logger.warning(f"[Webhook] SKU not found in internal catalog: {sku}")
            continue
            
        # Get latest demand signal to base the new one on
        latest_signal = DemandSignal.query.filter_by(product_id=product.id).order_by(DemandSignal.created_at.desc()).first()
        
        current_velocity = latest_signal.sku_velocity if latest_signal else 1.0
        new_velocity = current_velocity + (quantity * 0.1) # Bump velocity based on quantity ordered
        
        new_signal = DemandSignal(
            product_id=product.id,
            organization_id=product.organization_id,
            trend_score=latest_signal.trend_score if latest_signal else 0.5,
            seasonal_factor=latest_signal.seasonal_factor if latest_signal else 1.0,
            sku_velocity=new_velocity
        )
        
        db.session.add(new_signal)
        
        # Decrement inventory by quantity ordered to keep everything in sync
        if product.inventory_quantity >= quantity:
            product.inventory_quantity -= quantity
        else:
            # Auto restock
            product.inventory_quantity += 100
            product.inventory_quantity -= quantity
            
        # Create a Sale record
        sale = Sale(
            product_id=product.id,
            organization_id=product.organization_id,
            quantity=quantity,
            price_per_unit=product.current_price
        )
        db.session.add(sale)
            
        processed_skus.append({"sku": sku, "new_velocity": new_velocity})
        
    try:
        db.session.commit()
        logger.info(f"[Webhook] Successfully processed Shopify order. Updated SKUs: {processed_skus}")
        
        # Log to UI
        if not hasattr(current_app, "webhook_logs"):
            current_app.webhook_logs = []
            
        current_app.webhook_logs.insert(0, {
            "event": "orders/create",
            "topic": "Order Placed",
            "payload_id": f"shopify-ord-{data.get('id', 'unknown')}",
            "status": "processed",
            "ai_adjusted": True
        })
        current_app.webhook_logs = current_app.webhook_logs[:50]
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"[Webhook] DB error processing order: {str(e)}")
        return {"success": False, "message": "Database error"}, 500

    return {"success": True, "processed": processed_skus}, 200
