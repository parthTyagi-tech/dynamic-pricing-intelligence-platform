"""
Demand Forecast Agent
Analyzes demand signals, trend scores, seasonal factors, and SKU velocity.
"""
from typing import Dict, Any, List
from app.services.ai.client import async_structured_json_completion
from app.services.ai.prompts import DEMAND_FORECASTING_SYSTEM, demand_forecasting_prompt


def _mock_demand_analysis(product: dict, demand_signals: list) -> dict:
    """Fallback mock calculations when AI is unavailable."""
    if not demand_signals:
        return {
            "demand_level": "medium",
            "trend_direction": "stable",
            "avg_trend_score": 0.5,
            "avg_seasonal_factor": 1.0,
            "avg_velocity": 10.0,
            "demand_based_price_adjustment_pct": 0.0,
            "insights": "No demand signals available for analysis. Holding price steady."
        }

    trend_scores = [d.get("trend_score", 0.5) for d in demand_signals]
    seasonal_factors = [d.get("seasonal_factor", 1.0) for d in demand_signals]
    velocities = [d.get("sku_velocity", 0.0) for d in demand_signals]

    avg_trend = sum(trend_scores) / len(trend_scores)
    avg_season = sum(seasonal_factors) / len(seasonal_factors)
    avg_vel = sum(velocities) / len(velocities)

    # Determine trend direction and level based on score
    if avg_trend >= 0.75:
        trend_dir = "rising"
        demand_lvl = "high"
        adj = round((avg_trend - 0.5) * 15, 2)
    elif avg_trend <= 0.40:
        trend_dir = "declining"
        demand_lvl = "low"
        adj = round((avg_trend - 0.5) * 15, 2)
    else:
        trend_dir = "stable"
        demand_lvl = "medium"
        adj = 0.0

    return {
        "demand_level": demand_lvl,
        "trend_direction": trend_dir,
        "avg_trend_score": round(avg_trend, 2),
        "avg_seasonal_factor": round(avg_season, 2),
        "avg_velocity": round(avg_vel, 2),
        "demand_based_price_adjustment_pct": adj,
        "insights": f"Demand trend is {trend_dir} with velocity of {avg_vel:.1f} units/day. Seasonal multiplier is {avg_season:.2f}x."
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
    result = await async_structured_json_completion(
        system_prompt=DEMAND_FORECASTING_SYSTEM,
        user_prompt=prompt,
        agent_name="DemandForecastAgent"
    )

    if not result:
        result = _mock_demand_analysis(product, demand_signals)

    result["agent"] = "demand_forecast"
    return result
