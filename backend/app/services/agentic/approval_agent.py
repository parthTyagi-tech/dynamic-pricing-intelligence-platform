import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.extensions import db
from app.models.audit_log import AuditLog
from app.models.pricing_recommendation import PricingRecommendation, RecommendationStatus
from app.models.product import Product
from app.services.agentic.base_agent import BaseAgent
from app.services.agentic.catalog_update_agent import CatalogUpdateAgent
from app.services.agentic.notification_agent import NotificationAgent
from app.services.task_state.task_manager import TaskAccessDeniedError, get_task_manager

logger = logging.getLogger(__name__)


class ApprovalAgent(BaseAgent):
    """
    Coordinates Human-in-the-Loop Approval & Rejection.
    Enforces SEC-2 ownership validation before applying mutations.
    """

    def __init__(self):
        super().__init__(
            role="ApprovalAgent",
            goal="Oversee human approval decisions, enforce audit trails, and trigger catalog updates",
            available_tools=["approval_handler", "rejection_logger", "catalog_bridge"]
        )
        self.catalog_updater = CatalogUpdateAgent()
        self.notifier = NotificationAgent()

    async def approve(
        self,
        task_id: str,
        user_id: str,
        organization_id: str
    ) -> Dict[str, Any]:
        task_mgr = get_task_manager()
        # SEC-2: Validate ownership
        task = task_mgr.get_task(task_id, organization_id)

        rec = PricingRecommendation.query.filter_by(
            task_id=task_id,
            organization_id=organization_id
        ).first()

        if not rec:
            raise ValueError(f"No pending recommendation found for task {task_id}")

        product = Product.query.filter_by(
            id=rec.product_id,
            organization_id=organization_id
        ).first()

        old_price = float(product.current_price)

        # 1. Apply price update in database atomically (CatalogUpdateAgent)
        update_result = await self.catalog_updater.apply_price_change(
            task_id=task_id,
            recommendation_id=rec.id,
            organization_id=organization_id,
            user_id=user_id
        )

        # 2. Dispatch transactional notification (NotificationAgent)
        await self.notifier.send_approval_email(
            task_id=task_id,
            organization_id=organization_id,
            product=product.to_dict(),
            old_price=old_price,
            new_price=update_result["new_price"],
            confidence=rec.confidence,
            reasoning_text=rec.reasoning_text,
            user_id=user_id
        )

        task_mgr.update_status(task_id, "approved")

        await self.emit_event(
            task_id=task_id,
            product_id=product.id,
            organization_id=organization_id,
            event_type="user_approved",
            message=f"Recommendation approved by user {user_id}. Price updated to ₹{update_result['new_price']:,.2f}.",
            payload=update_result
        )

        return update_result

    async def reject(
        self,
        task_id: str,
        user_id: str,
        organization_id: str,
        reason: str
    ) -> Dict[str, Any]:
        task_mgr = get_task_manager()
        # SEC-2: Validate ownership
        task = task_mgr.get_task(task_id, organization_id)

        rec = PricingRecommendation.query.filter_by(
            task_id=task_id,
            organization_id=organization_id
        ).first()

        if not rec:
            raise ValueError(f"No pending recommendation found for task {task_id}")

        safe_reason = self.sanitize_output(reason or "Price rejected by user.")

        try:
            rec.status = RecommendationStatus.REJECTED
            rec.decided_at = datetime.now(timezone.utc)
            rec.decided_by = user_id

            # SEC-8: Audit log rejection
            audit_record = AuditLog(
                id=str(uuid.uuid4()),
                organization_id=organization_id,
                actor_user_id=user_id,
                action="recommendation_rejected",
                entity_type="pricing_recommendation",
                entity_id=rec.id,
                before_value={"status": "pending", "recommended_price": rec.recommended_price},
                after_value={"status": "rejected"},
                metadata_json={"rejection_reason": safe_reason, "task_id": task_id}
            )
            db.session.add(audit_record)
            db.session.commit()

            task_mgr.update_status(task_id, "rejected")

            await self.emit_event(
                task_id=task_id,
                product_id=rec.product_id,
                organization_id=organization_id,
                event_type="user_rejected",
                message=f"Recommendation rejected: {safe_reason}",
                payload={"reason": safe_reason, "audit_id": audit_record.id}
            )

            return {"status": "rejected", "reason": safe_reason, "audit_id": audit_record.id}

        except Exception as e:
            db.session.rollback()
            logger.error(f"[ApprovalAgent] Rejection error: {e}", exc_info=True)
            raise
