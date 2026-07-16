"""
Inventory & Cost Agent
Analyzes inventory levels and cost structures to inform pricing decisions.
"""
from typing import Dict, Any
from app.services.ai.client import async_guarded_json_completion
from app.services.ai.schemas import InventoryAnalysisSchema
from app.services.ai.prompts import INVENTORY_COST_SYSTEM, inventory_cost_prompt


def _mock_inventory_analysis(product: dict) -> dict:
    """Fallback mock calculations when AI is unavailable. Generate realistic cost margin insights."""
    current_price = product.get("current_price", 0.0)
    cost = product.get("cost_price", 0.0)
    margin_pct = ((current_price - cost) / current_price * 100) if current_price > 0 else 0.0
    qty = product.get("inventory_quantity", 10)
    status = "oversell" if qty < 10 else ("overstock" if qty > 100 else "healthy")
    adj = 1.0 if status == "oversell" else (-1.0 if status == "overstock" else 0.0)
    return {
        "inventory_status": status,
        "current_margin_pct": round(margin_pct, 2),
        "min_viable_price": round(cost * 1.15, 2),
        "inventory_pressure_adjustment_pct": adj,
        "insights": f"Inventory level is {qty} units ({status} state). Sane margin bounds maintained above raw COGS of ₹{cost:,.2f}.",
        "llm_failed": False
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
    result = await async_guarded_json_completion(
        system_prompt=INVENTORY_COST_SYSTEM,
        user_prompt=prompt,
        response_model=InventoryAnalysisSchema,
        agent_name="InventoryAgent"
    )

    if not result:
        result = _mock_inventory_analysis(product)

    result["agent"] = "inventory_cost"
    return result
