"""
Pricing Strategy Agent
Synthesizes market intelligence, demand forecasting, and inventory cost constraints to recommend an optimal price.
"""
from typing import Dict, Any
from app.services.ai.client import async_structured_json_completion
from app.services.ai.prompts import PRICING_STRATEGY_SYSTEM, pricing_strategy_prompt


def _mock_strategy_generation(
    product: dict,
    market_analysis: dict,
    demand_analysis: dict,
    inventory_analysis: dict,
    pricing_rules: dict
) -> dict:
    """Fallback mock strategy synthesis when AI is unavailable."""
    current_price = product.get("current_price", 0.0)

    market_adj = market_analysis.get("suggested_adjustment_pct", 0.0)
    demand_adj = demand_analysis.get("demand_based_price_adjustment_pct", 0.0)
    inv_adj = inventory_analysis.get("inventory_pressure_adjustment_pct", 0.0)
    
    # Check for competitor out of stock exploitation
    competitors = market_analysis.get("competitors", [])
    any_competitor_oos = any(not comp.get("in_stock", True) for comp in competitors)
    
    # Check for dead stock liquidation
    velocity = demand_analysis.get("avg_velocity", 1.0)
    inventory = product_data.get("inventory_quantity", 0)
    is_dead_stock = velocity < 0.5 and inventory > 30

    composite_adj = (market_adj * 0.35) + (demand_adj * 0.35) + (inv_adj * 0.30)
    
    if is_dead_stock:
        composite_adj = -20.0
    elif any_competitor_oos:
        composite_adj = 15.0
    else:
        composite_adj = max(min(composite_adj, 15.0), -15.0)
    
    recommended_price = round(current_price * (1.0 + composite_adj / 100.0), 2)

    if is_dead_stock:
        strategy = "liquidation"
        rationale = "Dead stock status detected. Aggressively marking down to clear inventory."
        confidence = 0.95
        risk = "low"
    elif any_competitor_oos:
        strategy = "exploit_monopoly"
        rationale = "Competitor out of stock detected. Raising prices to capture overflow demand."
        confidence = 0.92
        risk = "medium"
    elif inv_adj < -5.0:
        strategy = "clearance"
        rationale = f"Inventory level is critical. Recommending a discount to execute a clearance strategy."
        confidence = 0.88
        risk = "medium"
    elif demand_adj > 5.0 and inv_adj >= 0.0:
        strategy = "premium"
        rationale = f"High category demand and rising signals support a premium pricing posture to maximize margins."
        confidence = 0.94
        risk = "low"
    elif market_adj < -3.0:
        strategy = "penetration"
        rationale = f"Undercutting competitor averages to establish market position and boost conversion."
        confidence = 0.85
        risk = "high"
    elif abs(composite_adj) < 1.0:
        strategy = "maintain"
        rationale = f"Holding price steady. Market, demand, and inventory conditions are balanced."
        confidence = 0.97
        risk = "low"
    else:
        strategy = "competitive"
        rationale = f"Recommending competitive alignment price adjustments to reflect active competitor pricing movements."
        confidence = 0.90
        risk = "medium"

    return {
        "recommended_price": recommended_price,
        "price_change_pct": round(composite_adj, 2),
        "strategy": strategy,
        "rationale": rationale,
        "confidence_score": confidence,
        "risk_level": risk,
        "projected_volume_increase_pct": round(max(0.0, -composite_adj * 1.5), 1),
        "projected_monthly_profit_lift": round(abs(composite_adj * 12.5), 2)
    }


async def run(
    product: dict,
    market_analysis: dict,
    demand_analysis: dict,
    inventory_analysis: dict,
    pricing_rules: dict
) -> Dict[str, Any]:
    """
    Run strategy synthesis.
    """
    prompt = pricing_strategy_prompt(
        product,
        market_analysis,
        demand_analysis,
        inventory_analysis,
        pricing_rules
    )
    result = await async_structured_json_completion(
        system_prompt=PRICING_STRATEGY_SYSTEM,
        user_prompt=prompt,
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
