"""
Demand Forecast Agent
Analyzes demand signals, trend scores, seasonal factors, and SKU velocity.
"""
from typing import Dict, Any, List
from app.services.ai.client import async_guarded_json_completion
from app.services.ai.schemas import DemandAnalysisSchema
from app.services.ai.prompts import DEMAND_FORECASTING_SYSTEM, demand_forecasting_prompt


def _mock_demand_analysis(product: dict, demand_signals: list) -> dict:
    """Fallback mock calculations when AI is unavailable. Set neutral values to preserve current catalog price."""
    return {
        "demand_level": "medium",
        "trend_direction": "stable",
        "avg_trend_score": 0.5,
        "avg_seasonal_factor": 1.0,
        "avg_velocity": 0.0,
        "demand_based_price_adjustment_pct": 0.0,
        "insights": "Demand Forecast Agent failed. Held demand status at neutral stable.",
        "llm_failed": True
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
