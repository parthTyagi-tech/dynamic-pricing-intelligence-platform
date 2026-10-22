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

        # Enforce canonical SEC-9 margin floor compliance on approval
        from app.models.audit_loging import PricingRule
        from app.utils.security_guardrails import compute_price_floor, effective_min_margin_pct

        cost_price = float(product.cost_price or 0.0)
        org_rule = (
            PricingRule.query.filter_by(organization_id=organization_id).first()
            if organization_id
            else None
        )
        rule_fraction = org_rule.minimum_margin if org_rule else 0.15
        effective_pct = effective_min_margin_pct(product.min_margin_percentage, rule_fraction)
        floor = compute_price_floor(cost_price, effective_pct)

        if new_price < floor:
            logger.warning(
                f"[CatalogUpdateAgent] Recommended price {new_price:.2f} is below computed margin floor {floor:.2f} "
                f"(cost: {cost_price:.2f}, min margin: {effective_pct:.1f}%). "
                f"Clamping price to floor {floor:.2f} to guarantee SEC-9 compliance on approval."
            )
            new_price = floor
            rec.recommended_price = floor
            rec.margin_floor_applied = True
            rec.margin_floor_value = floor

        try:
            from app.services.pricing.price_writer import apply_price_change as execute_price_change
            res = execute_price_change(
                product=product,
                new_price=new_price,
                actor_user_id=user_id,
                source="catalog_update_agent",
                recommendation=rec,
                expected_base_price=rec.base_price,
                sanity_override=bool(rec.sanity_bound_flagged),
                reason=f"Approved for task {task_id}",
            )
            product.recommendation_status = "approved"
            rec.status = RecommendationStatus.APPROVED
            rec.decided_at = datetime.now(timezone.utc)
            rec.decided_by = user_id

            from app.models.recommendation import ApprovalAction
            approval_action = ApprovalAction(
                id=str(uuid.uuid4()),
                recommendation_id=rec.id,
                action_type="approve",
                previous_price=res["old_price"],
                executed_price=res["new_price"],
                approved_by=user_id,
                sku=product.sku,
                llm_statement=rec.reasoning_text or rec.rationale,
            )
            db.session.add(approval_action)
            db.session.commit()

            logger.info(
                f"[CatalogUpdateAgent] Successfully updated SKU {product.sku} price: "
                f"₹{res['old_price']:,.2f} -> ₹{res['new_price']:,.2f}"
            )

            result = {
                "product_id": product.id,
                "sku": product.sku,
                "old_price": res["old_price"],
                "new_price": res["new_price"],
                "history_id": res["history_id"],
                "audit_id": res["audit_id"],
                "action_id": approval_action.id,
            }

            await self.emit_event(
                task_id=task_id,
                product_id=product.id,
                organization_id=organization_id,
                event_type="price_updated",
                message=f"Price updated from ₹{res['old_price']:,.2f} to ₹{res['new_price']:,.2f}. Audit log #{res['audit_id'][:8]} created.",
                payload=result
            )

            return result

        except Exception as e:
            db.session.rollback()
            logger.error(f"[CatalogUpdateAgent] Failed to apply price update: {e}", exc_info=True)
            raise
