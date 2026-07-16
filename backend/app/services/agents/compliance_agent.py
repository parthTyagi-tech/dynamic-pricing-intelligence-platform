"""
Execution & Compliance Agent
Validates pricing recommendations against margin constraints, rules, and business floors.
"""
from typing import Dict, Any
from app.services.ai.client import async_guarded_json_completion
from app.services.ai.schemas import ComplianceSchema
from app.services.ai.prompts import COMPLIANCE_SYSTEM, compliance_prompt


def _mock_compliance_check(product: dict, recommended_price: float, pricing_rules: dict) -> dict:
    """Fallback mock compliance checker when AI is unavailable."""
    cost = product.get("cost_price", 0.0)
    min_margin = pricing_rules.get("minimum_margin", 0.15)

    margin_at_rec = ((recommended_price - cost) / recommended_price) if recommended_price > 0 else 0.0
    floor_met = margin_at_rec >= min_margin
    final_price = recommended_price
    violations = []
    notes = "Price recommendation satisfies organizational margin floors."

    if not floor_met:
        final_price = round(cost / (1.0 - min_margin), 2) if min_margin < 1.0 else cost
        violations.append(f"Recommended price of ₹{recommended_price:.2f} results in a margin of {margin_at_rec:.1%}, which violates the minimum margin constraint of {min_margin:.1%}.")
        notes = f"Price adjusted from ₹{recommended_price:.2f} to ₹{final_price:.2f} to enforce minimum margin constraints."

    return {
        "compliant": floor_met,
        "margin_at_recommended": round(margin_at_rec * 100, 2),
        "margin_floor_met": floor_met,
        "violations": violations,
        "final_recommended_price": final_price,
        "compliance_notes": notes,
        "llm_failed": False
    }


async def run(product: dict, recommended_price: float, pricing_rules: dict) -> Dict[str, Any]:
    """
    Run compliance check with programmatic mathematical verification.
    """
    cost = product.get("cost_price", 0.0)
    min_margin = pricing_rules.get("minimum_margin", 0.15)

    margin_at_rec = ((recommended_price - cost) / recommended_price) if recommended_price > 0 else 0.0
    floor_met = margin_at_rec >= min_margin

    prompt = compliance_prompt(product, recommended_price, pricing_rules)
    result = await async_guarded_json_completion(
        system_prompt=COMPLIANCE_SYSTEM,
        user_prompt=prompt,
        response_model=ComplianceSchema,
        agent_name="ComplianceAgent"
    )

    if not result:
        result = _mock_compliance_check(product, recommended_price, pricing_rules)

    # Mathematically verify and override to prevent LLM calculation/decimal errors
    result["margin_at_recommended"] = round(margin_at_rec * 100, 2)
    result["compliant"] = floor_met
    result["margin_floor_met"] = floor_met

    if floor_met:
        result["final_recommended_price"] = recommended_price
        result["violations"] = []
        result["compliance_notes"] = "Price recommendation satisfies organizational margin floors."
    else:
        final_price = round(cost / (1.0 - min_margin), 2) if min_margin < 1.0 else cost
        result["final_recommended_price"] = final_price
        result["violations"] = [
            f"Recommended price of ₹{recommended_price:.2f} results in a margin of {margin_at_rec:.1%}, which violates the minimum margin constraint of {min_margin:.1%}."
        ]
        result["compliance_notes"] = f"Price adjusted from ₹{recommended_price:.2f} to ₹{final_price:.2f} to enforce minimum margin constraints."

    result["agent"] = "execution_compliance"
    return result
