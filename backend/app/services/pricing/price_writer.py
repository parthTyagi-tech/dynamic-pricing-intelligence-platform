from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from app.extensions import db
from app.models.audit_loging import AuditLog, PricingRule
from app.models.price_history import PriceHistory
from app.models.product import Product
from app.models.recommendation import PricingRecommendation
from app.utils.security_guardrails import (
    atomic_ledger_write,
    check_sanity_bound,
    compute_price_floor,
    effective_min_margin_pct,
)

logger = logging.getLogger(__name__)


class PriceGuardrailError(Exception):
    """Base exception for all pricing guardrail violations."""


class BelowFloorError(PriceGuardrailError):
    """Raised when the target price is strictly below the computed margin floor."""


class SanityBoundError(PriceGuardrailError):
    """Raised when the price delta exceeds the sanity bound without explicit override."""


class StalePriceError(PriceGuardrailError):
    """Raised when the product price has drifted from expected_base_price (optimistic concurrency)."""


class AlreadyDecidedError(Exception):
    """Raised when a recommendation has already been approved, rejected, or is not in PENDING status."""


def apply_price_change(
    *,
    product: Product,
    new_price: float,
    actor_user_id: Optional[str] = None,
    source: str,
    recommendation: Optional[PricingRecommendation] = None,
    expected_base_price: Optional[float] = None,
    sanity_override: bool = False,
    reason: str = "",
) -> dict[str, Any]:
    """
    The canonical and ONLY mutator of Product.current_price in the system.

    In ONE atomic transaction:
      1. Sanity evaluation: check_sanity_bound (|delta| > 50%).
         Evaluated first so any out-of-bound drop flags recommendation.sanity_bound_flagged.
         If flagged and not sanity_override, raises SanityBoundError.
      2. Floor check: compute_price_floor(cost_price, effective_margin).
         If new_price < floor, raises BelowFloorError (never silently clamp here).
      3. Optimistic concurrency: if expected_base_price is provided and
         abs(current_price - expected_base_price) > 0.005, raises StalePriceError.
      4. Mutates product.current_price = new_price.
      5. Appends PriceHistory row.
      6. Appends AuditLog row (action='price_changed').

    Returns:
        dict: {"old_price": float, "new_price": float, "history_id": str, "audit_id": str}
    """
    if product is None:
        raise ValueError("Product must not be None")

    old_price = float(product.current_price or 0.0)
    target_price = round(float(new_price), 2)

    # 1. Sanity check: evaluate first so sanity_bound_flagged is recorded on recommendation
    sanity_flagged, delta_pct = check_sanity_bound(old_price, target_price)
    if recommendation is not None:
        recommendation.sanity_bound_flagged = sanity_flagged

    if sanity_flagged and not sanity_override:
        raise SanityBoundError(
            f"New price {target_price:.2f} deviates {delta_pct:.1%} from current price "
            f"{old_price:.2f}, exceeding the 50% sanity bound without an authorized override."
        )

    # 2. Floor check
    cost_price = float(product.cost_price or 0.0)
    org_rule = (
        PricingRule.query.filter_by(organization_id=product.organization_id).first()
        if product.organization_id
        else None
    )
    rule_fraction = org_rule.minimum_margin if org_rule else 0.15
    effective_pct = effective_min_margin_pct(product.min_margin_percentage, rule_fraction)
    floor = compute_price_floor(cost_price, effective_pct)

    if target_price < floor:
        raise BelowFloorError(
            f"New price {target_price:.2f} is below computed margin floor {floor:.2f} "
            f"(cost: {cost_price:.2f}, min margin: {effective_pct:.1f}%)."
        )

    # 3. Optimistic concurrency check
    if expected_base_price is not None:
        if abs(old_price - float(expected_base_price)) > 0.005:
            raise StalePriceError(
                f"Base price has drifted since recommendation was created: "
                f"expected {float(expected_base_price):.2f}, actual {old_price:.2f}."
            )

    # 4, 5, 6. Atomic Ledger Write
    history_id = str(uuid.uuid4())
    audit_id = str(uuid.uuid4())

    with atomic_ledger_write():
        # Canonical mutation of Product.current_price
        product.current_price = target_price

        # PriceHistory
        snapshot = (
            recommendation.platform_prices_snapshot
            if recommendation and recommendation.platform_prices_snapshot
            else {}
        )
        history = PriceHistory(
            id=history_id,
            product_id=product.id,
            organization_id=product.organization_id,
            old_price=old_price,
            new_price=target_price,
            platform_prices=snapshot,
            approved_by=actor_user_id,
            recommendation_id=recommendation.id if recommendation else None,
        )
        db.session.add(history)

        # AuditLog
        audit = AuditLog(
            id=audit_id,
            user_id=actor_user_id,
            organization_id=product.organization_id,
            action="price_changed",
            entity_type="product",
            entity_id=product.id,
            before_value={"current_price": old_price},
            after_value={"current_price": target_price},
            extra_metadata={
                "source": source,
                "reason": reason or "",
                "recommendation_id": recommendation.id if recommendation else None,
                "sanity_override": bool(sanity_override),
                "margin_floor": floor,
                "effective_min_margin_pct": effective_pct,
            },
        )
        db.session.add(audit)
        db.session.flush()

    logger.info(
        f"[PriceWriter] Applied price change for product {product.id} "
        f"({old_price:.2f} -> {target_price:.2f}) from {source}. History: {history_id}"
    )

    return {
        "old_price": old_price,
        "new_price": target_price,
        "history_id": history_id,
        "audit_id": audit_id,
    }
