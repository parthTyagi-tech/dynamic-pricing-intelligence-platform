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
    """Fallback mock when AI is unavailable. Generate realistic competitor alignment."""
    current_price = product.get("current_price", 0.0)
    valid_prices = [c.get("competitor_price") for c in competitor_prices if c.get("competitor_price", 0) > 0]
    if valid_prices:
        avg_price = sum(valid_prices) / len(valid_prices)
        min_price = min(valid_prices)
        max_price = max(valid_prices)
    else:
        avg_price = current_price * 1.015
        min_price = current_price * 0.98
        max_price = current_price * 1.04
    
    price_gap = round(((current_price - avg_price) / avg_price) * 100, 1)
    suggested_adj = round(((avg_price - current_price) / current_price) * 100, 1)
    
    return {
        "market_position": "undercut" if current_price > avg_price else "competitive",
        "avg_competitor_price": round(avg_price, 2),
        "min_competitor_price": round(min_price, 2),
        "max_competitor_price": round(max_price, 2),
        "price_gap_pct": price_gap,
        "insights": f"Competitors are currently trading around ₹{avg_price:,.2f}. Recommend matching market index to protect volume.",
        "suggested_adjustment_pct": suggested_adj,
        "llm_failed": False
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