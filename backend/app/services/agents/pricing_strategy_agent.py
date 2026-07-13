"""
Pricing Strategy Agent
Synthesizes market intelligence, demand forecasting, and inventory cost constraints to recommend an optimal price.
"""
from typing import Dict, Any
from app.services.ai.client import async_guarded_json_completion
from app.services.ai.schemas import PricingStrategySchema
from app.services.ai.prompts import PRICING_STRATEGY_SYSTEM, pricing_strategy_prompt


def _mock_strategy_generation(
    product: dict,
    market_analysis: dict,
    demand_analysis: dict,
    inventory_analysis: dict,
    pricing_rules: dict
) -> dict:
    """Fallback mock strategy synthesis when AI is unavailable. Returns maintain current catalog price."""
    current_price = product.get("current_price", 0.0)
    return {
        "recommended_price": current_price,
        "price_change_pct": 0.0,
        "strategy": "maintain",
        "rationale": "LLM agent execution failed. Falling back to the product's actual catalog price to maintain stability.",
        "confidence_score": 1.0,
        "risk_level": "low",
        "projected_volume_increase_pct": 0.0,
        "projected_monthly_profit_lift": 0.0,
        "llm_failed": True
    }


async def run(
    product: dict,
    market_analysis: dict,
    demand_analysis: dict,
    inventory_analysis: dict,
    pricing_rules: dict,
    sales_history: list = None,
) -> Dict[str, Any]:
    """
    Run strategy synthesis.
    """
    if (market_analysis.get("llm_failed") or 
        demand_analysis.get("llm_failed") or 
        inventory_analysis.get("llm_failed")):
        result = _mock_strategy_generation(
            product,
            market_analysis,
            demand_analysis,
            inventory_analysis,
            pricing_rules
        )
        result["agent"] = "pricing_strategy"
        return result

    prompt = pricing_strategy_prompt(
        product,
        market_analysis,
        demand_analysis,
        inventory_analysis,
        pricing_rules,
        sales_history
    )
    result = await async_guarded_json_completion(
        system_prompt=PRICING_STRATEGY_SYSTEM,
        user_prompt=prompt,
        response_model=PricingStrategySchema,
        agent_name="PricingStrategyAgent"
    )

    if not result:
        result = _mock_strategy_generation(
            product,
            market_analysis,
            demand_analysis,
            inventory_analysis,
            pricing_rules
        )

    result["agent"] = "pricing_strategy"
    return result
