"""
Execution & Compliance Agent
Validates pricing recommendations against margin constraints, rules, and business floors.
"""
from typing import Dict, Any
from app.services.ai.client import async_guarded_json_completion
from app.services.ai.schemas import ComplianceSchema
from app.services.ai.prompts import COMPLIANCE_SYSTEM, compliance_prompt
from app.utils.security_guardrails import compute_price_floor, effective_min_margin_pct


def _mock_compliance_check(product: dict, recommended_price: float, pricing_rules: dict) -> dict:
    """Fallback mock compliance checker when AI is unavailable."""
    cost = float(product.get("cost_price", 0.0) or 0.0)
    rule_margin = pricing_rules.get("minimum_margin", 0.15) if pricing_rules else 0.15
    prod_margin = product.get("min_margin_percentage")
    eff_pct = effective_min_margin_pct(prod_margin, rule_margin)
    floor_price = compute_price_floor(cost, eff_pct)
    floor_met = recommended_price >= floor_price
    final_price = recommended_price
    violations = []
    notes = "Price recommendation satisfies organizational margin floors."

    margin_at_rec = ((recommended_price - cost) / recommended_price) if recommended_price > 0 else 0.0

    if not floor_met:
        final_price = floor_price
        violations.append(
            f"Recommended price of ₹{recommended_price:.2f} violates the minimum margin constraint (floor: ₹{floor_price:.2f}, margin: {eff_pct:.1f}%)."
        )
        notes = f"Price adjusted from ₹{recommended_price:.2f} to ₹{final_price:.2f} to enforce minimum margin constraints."

    mock_dict = {
        "compliant": floor_met,
        "margin_at_recommended": round(margin_at_rec * 100, 2),
        "margin_floor_met": floor_met,
        "violations": violations,
        "final_recommended_price": final_price,
        "compliance_notes": notes,
    }
    validated = ComplianceSchema.model_validate(mock_dict).model_dump()
    validated["llm_failed"] = True
    validated["degraded"] = True
    return validated


async def run(product: dict, recommended_price: float, pricing_rules: dict) -> Dict[str, Any]:
    """
    Run compliance check with programmatic mathematical verification.
    """
    cost = float(product.get("cost_price", 0.0) or 0.0)
    rule_margin = pricing_rules.get("minimum_margin", 0.15) if pricing_rules else 0.15
    prod_margin = product.get("min_margin_percentage")
    eff_pct = effective_min_margin_pct(prod_margin, rule_margin)
    floor_price = compute_price_floor(cost, eff_pct)
    floor_met = recommended_price >= floor_price

    margin_at_rec = ((recommended_price - cost) / recommended_price) if recommended_price > 0 else 0.0

    prompt = compliance_prompt(product, recommended_price, pricing_rules)
    result = await async_guarded_json_completion(
        system_prompt=COMPLIANCE_SYSTEM,
        user_prompt=prompt,
        response_model=ComplianceSchema,
        agent_name="ComplianceAgent"
    )

    if not result:
        result = _mock_compliance_check(product, recommended_price, pricing_rules)
    else:
        result["llm_failed"] = False
        result["degraded"] = False

    # Mathematically verify and override to prevent LLM calculation/decimal errors
    result["margin_at_recommended"] = round(margin_at_rec * 100, 2)
    result["compliant"] = floor_met
    result["margin_floor_met"] = floor_met

    if floor_met:
        result["final_recommended_price"] = recommended_price
        result["violations"] = []
        result["compliance_notes"] = "Price recommendation satisfies organizational margin floors."
    else:
        final_price = floor_price
        result["final_recommended_price"] = final_price
        result["violations"] = [
            f"Recommended price of ₹{recommended_price:.2f} violates the minimum margin constraint (floor: ₹{floor_price:.2f}, margin: {eff_pct:.1f}%)."
        ]
        result["compliance_notes"] = f"Price adjusted from ₹{recommended_price:.2f} to ₹{final_price:.2f} to enforce minimum margin constraints."

    result["agent"] = "execution_compliance"
    return result

