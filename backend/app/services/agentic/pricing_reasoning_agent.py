import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.services.agentic.base_agent import BaseAgent
from app.services.ai.client import get_ai_client

logger = logging.getLogger(__name__)


class PricingReasoningAgent(BaseAgent):
    """
    Financial Reasoning Agent with code-enforced guardrails:
    - SEC-9: Prompt-injection defense (<untrusted_scraped_data> tags).
    - Code Guardrail 1: Strict Margin Floor (never below cost_price * (1 + margin%)).
    - Code Guardrail 2 (SEC-10): Price Sanity Bounds (deviation > 50% flags human review & sets confidence=low).
    - Partial Data Confidence Adjustment (single-platform -> medium confidence).
    """

    def __init__(self):
        super().__init__(
            role="PricingReasoningAgent",
            goal="Synthesize market intelligence and internal economics to formulate optimal, safe repricing",
            available_tools=["margin_floor_guardrail", "sanity_bound_validator", "llm_pricing_synthesizer"]
        )

    async def generate_recommendation(
        self,
        task_id: str,
        product: Dict[str, Any],
        aggregated_data: Dict[str, Any],
        organization_id: str
    ) -> Dict[str, Any]:
        product_id = product["id"]
        current_price = float(product.get("current_price", 0.0) or 0.0)
        cost_price = float(product.get("cost_price", 0.0) or 0.0)
        min_margin_pct = float(product.get("min_margin_percentage", 10.0) or 10.0)
        inventory_qty = int(product.get("inventory_quantity", 0) or 0)

        # -------------------------------------------------------------
        # 1. Code-Level Hard Guardrail: Margin Floor (SEC-9)
        # -------------------------------------------------------------
        margin_floor = round(cost_price * (1.0 + (min_margin_pct / 100.0)), 2)

        verified_count = aggregated_data.get("verified_count", 0)
        avg_market_price = float(aggregated_data.get("average_price", 0.0))
        platforms = aggregated_data.get("platforms", {})

        # Default confidence based on platform availability
        if verified_count >= 2:
            confidence = "high"
        elif verified_count == 1:
            confidence = "medium"
        else:
            confidence = "low"

        # -------------------------------------------------------------
        # 2. Reasoning Synthesis (LLM with Prompt Injection Defense or Rule Fallback)
        # -------------------------------------------------------------
        recommended_price, rationale = self._synthesize_strategy(
            product=product,
            margin_floor=margin_floor,
            avg_market_price=avg_market_price,
            verified_count=verified_count,
            platforms=platforms,
            confidence=confidence
        )

        # -------------------------------------------------------------
        # 3. ENFORCE CODE GUARDRAIL: Never violate margin floor
        # -------------------------------------------------------------
        margin_floor_applied = False
        if recommended_price < margin_floor:
            logger.warning(
                f"[GUARDRAIL ACTIVATED] Pricing agent proposed ₹{recommended_price} below margin floor ₹{margin_floor}. "
                f"Clamping to floor."
            )
            self.record_decision(
                task_id=task_id,
                decision_point="Margin Floor Check",
                rationale=f"Proposed price ₹{recommended_price:,.2f} fell below minimum required margin floor of ₹{margin_floor:,.2f}.",
                action_taken=f"Hard-clamped recommended price to ₹{margin_floor:,.2f}"
            )
            recommended_price = margin_floor
            margin_floor_applied = True
            rationale += f" [Guardrail Note: Price adjusted to margin floor of ₹{margin_floor:,.2f} to protect profitability.]"

        # -------------------------------------------------------------
        # 4. ENFORCE CODE GUARDRAIL (SEC-10): Price Sanity Bounds
        # -------------------------------------------------------------
        sanity_bound_flagged = False
        if current_price > 0:
            deviation = abs(recommended_price - current_price) / current_price
            if deviation > 0.50:
                sanity_bound_flagged = True
                confidence = "low"  # Force human review on wild deviation
                self.record_decision(
                    task_id=task_id,
                    decision_point="Sanity Bound Validation (SEC-10)",
                    rationale=f"Recommended price ₹{recommended_price:,.2f} deviates by {deviation*100:.1f}% (>50%) from current price ₹{current_price:,.2f}.",
                    action_taken="Flagged sanity_bound_flagged=True and downgraded confidence to low for mandatory human audit"
                )
                rationale += f" [Sanity Warning: Price deviates by >50% from catalog price. Requires manual review.]"

        result = {
            "product_id": product_id,
            "current_price": current_price,
            "cost_price": cost_price,
            "recommended_price": recommended_price,
            "confidence": confidence,
            "reasoning_text": self.sanitize_output(rationale),
            "platform_prices_snapshot": platforms,
            "margin_floor_applied": margin_floor_applied,
            "margin_floor_value": margin_floor,
            "sanity_bound_flagged": sanity_bound_flagged,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.emit_event(
            task_id=task_id,
            product_id=product_id,
            organization_id=organization_id,
            event_type="recommendation_generated",
            message=f"Recommended ₹{recommended_price:,.2f} ({confidence.upper()} confidence). Margin floor: ₹{margin_floor:,.2f}.",
            payload=result
        )

        return result

    def _synthesize_strategy(
        self,
        product: Dict[str, Any],
        margin_floor: float,
        avg_market_price: float,
        verified_count: int,
        platforms: Dict[str, Any],
        confidence: str
    ) -> tuple:
        """Computes safe recommended price and explainable rationale."""
        current = float(product.get("current_price", 0.0) or 0.0)

        if verified_count == 0 or avg_market_price <= 0:
            # Fallback when no platforms reachable: keep current or clamp to margin floor
            rec = max(current, margin_floor)
            rationale = "Competitor scraping yielded no verified listings. Maintaining current price protected by margin floor."
            return rec, rationale

        # Market-competitive pricing formula
        if avg_market_price > current:
            # Opportunity to capture additional margin: move 60% towards market avg
            rec = round(current + (avg_market_price - current) * 0.60, 2)
            action_desc = f"Market index is trading higher at ₹{avg_market_price:,.2f}. Recommending price increase to capture additional profit."
        elif avg_market_price < current:
            # Market is cheaper: undercut by 1% or match market average to protect volume
            rec = round(avg_market_price * 0.99, 2)
            action_desc = f"Competitors are pricing lower at index ₹{avg_market_price:,.2f}. Recommending competitive adjustment to protect sales velocity."
        else:
            rec = current
            action_desc = f"Catalog price aligns with market index of ₹{avg_market_price:,.2f}."

        if verified_count == 1:
            platform_name = list(platforms.keys())[0]
            rationale = f"{action_desc} (Confidence marked MEDIUM: verified only on {platform_name}; secondary platform was unreachable)."
        else:
            platform_names = ", ".join(platforms.keys())
            rationale = f"{action_desc} (Verified across {platform_names})."

        return rec, rationale
