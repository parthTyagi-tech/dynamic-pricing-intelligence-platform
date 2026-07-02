"""
Market Intelligence Agent
Analyzes competitor pricing and market position.
"""
import random
from typing import Dict, Any, List
from app.services.ai.client import async_structured_json_completion
from app.services.ai.prompts import MARKET_INTELLIGENCE_SYSTEM, market_intelligence_prompt


def _mock_market_analysis(product: dict, competitor_prices: list) -> dict:
    """Fallback mock when AI is unavailable."""
    prices = [c.get("competitor_price", product["current_price"]) for c in competitor_prices]
    avg = sum(prices) / len(prices) if prices else product["current_price"]
    gap = ((product["current_price"] - avg) / avg * 100) if avg > 0 else 0

    return {
        "market_position": "competitive" if abs(gap) < 5 else ("leader" if gap < 0 else "lagging"),
        "avg_competitor_price": round(avg, 2),
        "min_competitor_price": round(min(prices), 2) if prices else product["current_price"],
        "max_competitor_price": round(max(prices), 2) if prices else product["current_price"],
        "price_gap_pct": round(gap, 2),
        "insights": f"Our price is {'above' if gap > 0 else 'below'} market average by {abs(gap):.1f}%.",
        "suggested_adjustment_pct": round(-gap * 0.5, 2),
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
    result = await async_structured_json_completion(
        system_prompt=MARKET_INTELLIGENCE_SYSTEM,
        user_prompt=prompt,
        agent_name="MarketIntelligenceAgent"
    )

    if not result:
        result = _mock_market_analysis(product, competitor_prices)

    result["agent"] = "market_intelligence"
    result["competitors"] = competitor_prices
    return result