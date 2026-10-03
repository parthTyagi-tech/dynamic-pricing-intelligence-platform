import json
import logging
import os
import aiohttp

logger = logging.getLogger(__name__)

LANGFLOW_API_URL = os.environ.get("LANGFLOW_API_URL", "http://langflow:7860/api/v1/run")
# Replace with the actual Flow ID created in Langflow
DEFAULT_FLOW_ID = os.environ.get("LANGFLOW_PRICING_FLOW_ID", "default_flow_id")


async def trigger_pricing_flow(product_data: dict, market_data: dict, flow_id: str = DEFAULT_FLOW_ID) -> dict:
    """
    Triggers a Langflow pipeline to generate a pricing strategy.
    Replaces the local asyncio.gather hardcoded agents.
    """
    base_price = float(product_data.get("current_price", product_data.get("price", 0.0)) or 0.0)

    payload = {
        "input_value": json.dumps({"product": product_data, "market": market_data}),
        "input_type": "text",
        "output_type": "text",
        "tweaks": {}
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{LANGFLOW_API_URL}/{flow_id}", json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    # Parse the langflow output
                    message_text = result.get("outputs", [{}])[0].get("outputs", [{}])[0].get("results", {}).get("message", {}).get("text", "{}")
                    try:
                        return json.loads(message_text)
                    except json.JSONDecodeError:
                        return {"recommended_price": base_price, "strategy_explanation": message_text}
                else:
                    error_text = await response.text()
                    logger.error(f"[Langflow Client] Error: {response.status} - {error_text}")
                    return {"recommended_price": base_price, "strategy_explanation": f"Langflow Error: {response.status}"}
    except Exception as e:
        logger.error(f"[Langflow Client] Request failed: {e}", exc_info=True)
        return {"recommended_price": base_price, "strategy_explanation": "Langflow unavailable. Fallback to base price."}
