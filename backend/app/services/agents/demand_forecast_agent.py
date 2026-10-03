"""
Demand Forecast Agent
Analyzes demand signals, trend scores, seasonal factors, and SKU velocity.
"""
from typing import Dict, Any, List
from app.services.ai.client import async_guarded_json_completion
from app.services.ai.schemas import DemandAnalysisSchema
from app.services.ai.prompts import DEMAND_FORECASTING_SYSTEM, demand_forecasting_prompt


def _mock_demand_analysis(product: dict, demand_signals: list) -> dict:
    """Fallback mock calculations when AI is unavailable. Generate realistic demand factors."""
    velocities = [float(s.get("velocity", 1.2) or 1.2) for s in demand_signals] if demand_signals else [1.5]
    avg_vel = sum(velocities) / len(velocities)
    
    # Must be Literal["rising", "stable", "declining"]
    trend_dir = "rising" if avg_vel > 1.8 else ("declining" if avg_vel < 1.0 else "stable")
    demand_lvl = "high" if avg_vel > 2.0 else ("low" if avg_vel < 1.0 else "medium")

    mock_dict = {
        "demand_level": demand_lvl,
        "trend_direction": trend_dir,
        "avg_trend_score": 0.72 if avg_vel > 1.8 else 0.55,
        "avg_seasonal_factor": 1.05,
        "avg_velocity": round(avg_vel, 2),
        "demand_based_price_adjustment_pct": 1.5 if avg_vel > 1.8 else 0.0,
        "insights": "Demand metrics indicate solid, stable purchasing velocity. Consumer sentiment supports minor price elasticity adjustments.",
    }
    validated = DemandAnalysisSchema.model_validate(mock_dict).model_dump()
    validated["llm_failed"] = True
    validated["degraded"] = True
    return validated


async def run(product: dict, demand_signals: List[dict]) -> Dict[str, Any]:
    """
    Run demand forecasting analysis.

    Args:
        product: dict with product details
        demand_signals: list of demand signal dicts

    Returns:
        Structured analysis dict
    """
    prompt = demand_forecasting_prompt(product, demand_signals)
    result = await async_guarded_json_completion(
        system_prompt=DEMAND_FORECASTING_SYSTEM,
        user_prompt=prompt,
        response_model=DemandAnalysisSchema,
        agent_name="DemandForecastAgent"
    )

    if not result:
        result = _mock_demand_analysis(product, demand_signals)
    else:
        result["llm_failed"] = False
        result["degraded"] = False

    result["agent"] = "demand_forecast"
    return result
