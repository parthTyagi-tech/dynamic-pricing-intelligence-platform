import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.price_history import PriceHistory
from app.models.pricing_recommendation import PricingRecommendation, RecommendationStatus
from app.models.product import Product
from app.services.agentic.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CatalogUpdateAgent(BaseAgent):
    """
    Applies approved price changes to the catalog with atomic consistency.
    Guarantees SEC-8 compliance:
    1. Updates Product.current_price
    2. Appends immutable PriceHistory row
    3. Writes AuditLog entry
    All within a single ACID transaction (all or nothing).
    """

    def __init__(self):
        super().__init__(
            role="CatalogUpdateAgent",
            goal="Atomically commit approved price adjustments and persist immutable price audit histories",
            available_tools=["atomic_transaction_executor", "audit_logger"]
        )

    async def apply_price_change(
        self,
        task_id: str,
        recommendation_id: str,
        organization_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        rec = PricingRecommendation.query.filter_by(
            id=recommendation_id,
            organization_id=organization_id
        ).first()

        if not rec:
            raise ValueError(f"PricingRecommendation {recommendation_id} not found for Org {organization_id}")

        product = Product.query.filter_by(
            id=rec.product_id,
            organization_id=organization_id
        ).first()

        if not product:
            raise ValueError(f"Product {rec.product_id} not found for Org {organization_id}")

        old_price = float(product.current_price)
        new_price = float(rec.recommended_price)

        try:
            # 1. Update Product price
            product.current_price = new_price
            product.recommendation_status = "approved"

            # 2. Append immutable PriceHistory row
            history_record = PriceHistory(
                id=str(uuid.uuid4()),
                product_id=product.id,
                organization_id=organization_id,
                old_price=old_price,
                new_price=new_price,
                platform_prices=rec.platform_prices_snapshot or {},
                approved_by=user_id,
                recommendation_id=rec.id,
            )
            db.session.add(history_record)

            # 3. Update Recommendation status
            rec.status = RecommendationStatus.APPROVED
            rec.decided_at = datetime.now(timezone.utc)
            rec.decided_by = user_id

            # 4. Write AuditLog (SEC-8)
            audit_record = AuditLog(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                actor_user_id=user_id,
                action="price_approved",
                entity_type="product",
                entity_id=product.id,
                before_value={"current_price": old_price},
                after_value={"current_price": new_price},
                metadata_json={
                    "recommendation_id": rec.id,
                    "task_id": task_id,
                    "confidence": rec.confidence,
                    "margin_floor_applied": rec.margin_floor_applied,
                }
            )
            db.session.add(audit_record)

            # Commit all changes atomically
            db.session.commit()

            logger.info(
                f"[CatalogUpdateAgent] Successfully updated SKU {product.sku} price: "
                f"₹{old_price:,.2f} -> ₹{new_price:,.2f}"
            )

            result = {
                "product_id": product.id,
                "sku": product.sku,
                "old_price": old_price,
                "new_price": new_price,
                "history_id": history_record.id,
                "audit_id": audit_record.id,
            }

            await self.emit_event(
                task_id=task_id,
                product_id=product.id,
                organization_id=organization_id,
                event_type="price_updated",
                message=f"Price updated from ₹{old_price:,.2f} to ₹{new_price:,.2f}. Audit log #{audit_record.id[:8]} created.",
                payload=result
            )

            return result

        except Exception as e:
            db.session.rollback()
            logger.error(f"[CatalogUpdateAgent] Failed to apply price update: {e}", exc_info=True)
            raise
