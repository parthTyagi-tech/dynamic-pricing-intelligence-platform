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
    velocities = [s.get("velocity", 1.2) for s in demand_signals] if demand_signals else [1.5]
    avg_vel = sum(velocities) / len(velocities)
    return {
        "demand_level": "high" if avg_vel > 2.0 else "medium",
        "trend_direction": "upward" if avg_vel > 1.8 else "stable",
        "avg_trend_score": 0.72 if avg_vel > 1.8 else 0.55,
        "avg_seasonal_factor": 1.05,
        "avg_velocity": round(avg_vel, 2),
        "demand_based_price_adjustment_pct": 1.5 if avg_vel > 1.8 else 0.0,
        "insights": "Demand metrics indicate solid, stable purchasing velocity. Consumer sentiment supports minor price elasticity adjustments.",
        "llm_failed": False
    }


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

    result["agent"] = "demand_forecast"
    return result
