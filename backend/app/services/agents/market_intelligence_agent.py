"""
Market Intelligence Agent
Analyzes competitor pricing and market position.
"""
import random
from typing import Dict, Any, List
from app.services.ai.client import async_guarded_json_completion
from app.services.ai.schemas import MarketAnalysisSchema
from app.services.ai.prompts import MARKET_INTELLIGENCE_SYSTEM, market_intelligence_prompt


def _mock_market_analysis(product: dict, competitor_prices: list) -> dict:
    """Fallback mock when AI is unavailable. Set neutral values to preserve current catalog price."""
    current_price = product.get("current_price", 0.0)
    return {
        "market_position": "stable",
        "avg_competitor_price": current_price,
        "min_competitor_price": current_price,
        "max_competitor_price": current_price,
        "price_gap_pct": 0.0,
        "insights": "Market Intelligence Agent failed. Standardized to product catalog price.",
        "suggested_adjustment_pct": 0.0,
        "llm_failed": True
    }


async def run(product: dict, competitor_prices: List[dict]) -> Dict[str, Any]:
    """
    Run market intelligence analysis.

    Args:
        product: dict with product fields
        competitor_prices: list of competitor price dicts

    Returns:
        Structured analysis dict
    """
    if not competitor_prices:
        return {
            "market_position": "unknown",
            "avg_competitor_price": product.get("current_price", 0),
            "min_competitor_price": product.get("current_price", 0),
            "max_competitor_price": product.get("current_price", 0),
            "price_gap_pct": 0.0,
            "insights": "No competitor data available.",
            "suggested_adjustment_pct": 0.0,
            "agent": "market_intelligence",
        }

    prompt = market_intelligence_prompt(product, competitor_prices)
    result = await async_guarded_json_completion(
        system_prompt=MARKET_INTELLIGENCE_SYSTEM,
        user_prompt=prompt,
        response_model=MarketAnalysisSchema,
        agent_name="MarketIntelligenceAgent"
    )

    if not result:
        result = _mock_market_analysis(product, competitor_prices)

    result["agent"] = "market_intelligence"
    result["competitors"] = competitor_prices
    return result