"""
Inventory & Cost Agent
Analyzes inventory levels and cost structures to inform pricing decisions.
"""
from typing import Dict, Any
from app.services.ai.client import async_structured_json_completion
from app.services.ai.prompts import INVENTORY_COST_SYSTEM, inventory_cost_prompt


def _mock_inventory_analysis(product: dict) -> dict:
    """Fallback mock calculations when AI is unavailable."""
    qty = product.get("inventory_quantity", 0)
    current_price = product.get("current_price", 0.0)
    cost = product.get("cost_price", 0.0)
    min_margin = product.get("min_margin_percentage", 10.0) / 100.0

    margin_pct = ((current_price - cost) / current_price * 100) if current_price > 0 else 0.0
    min_viable_price = round(cost / (1.0 - min_margin), 2) if min_margin < 1.0 else cost

    if qty <= 0:
        status = "out_of_stock"
        adj = 0.0
        insights = "Product is out of stock. Recommend holding price and restocking."
    elif qty < 10:
        status = "low_stock"
        adj = 5.0
        insights = f"Inventory count ({qty}) is critically low. Increasing price to slow velocity."
    elif qty > 100:
        status = "overstock"
        adj = -8.0
        insights = f"Overstock detected ({qty} units). Discounting price to increase velocity and clear storage."
    else:
        status = "healthy"
        adj = 0.0
        insights = f"Stock levels are healthy ({qty} units) and margins meet the min viability thresholds."

    return {
        "inventory_status": status,
        "current_margin_pct": round(margin_pct, 2),
        "min_viable_price": min_viable_price,
        "inventory_pressure_adjustment_pct": adj,
        "insights": insights
    }


async def run(product: dict) -> Dict[str, Any]:
    """
    Run inventory and cost analysis.

    Args:
        product: dict with product details

    Returns:
        Structured analysis dict
    """
    product_formatted = {
        "name": product.get("name"),
        "sku": product.get("sku"),
        "current_price": product.get("current_price"),
        "cost_price": product.get("cost_price"),
        "inventory_count": product.get("inventory_quantity"),
        "margin": ((product.get("current_price", 0.0) - product.get("cost_price", 0.0)) / product.get("current_price", 1.0))
    }

    prompt = inventory_cost_prompt(product_formatted)
    result = await async_structured_json_completion(
        system_prompt=INVENTORY_COST_SYSTEM,
        user_prompt=prompt,
        agent_name="InventoryAgent"
    )

    if not result:
        result = _mock_inventory_analysis(product)

    result["agent"] = "inventory_cost"
    return result
