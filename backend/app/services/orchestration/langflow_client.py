import os
import aiohttp

LANGFLOW_API_URL = os.environ.get("LANGFLOW_API_URL", "http://langflow:7860/api/v1/run")
# Replace with the actual Flow ID created in Langflow
DEFAULT_FLOW_ID = os.environ.get("LANGFLOW_PRICING_FLOW_ID", "default_flow_id")

async def trigger_pricing_flow(product_data: dict, market_data: dict, flow_id: str = DEFAULT_FLOW_ID) -> dict:
    """
    Triggers a Langflow pipeline to generate a pricing strategy.
    Replaces the local asyncio.gather hardcoded agents.
    """
    payload = {
        "input_value": str({"product": product_data, "market": market_data}),
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
                    # Assuming the flow returns a JSON string in the message text
                    message_text = result.get("outputs", [{}])[0].get("outputs", [{}])[0].get("results", {}).get("message", {}).get("text", "{}")
                    
                    import json
                    try:
                        return json.loads(message_text)
                    except json.JSONDecodeError:
                        return {"recommended_price": product_data.get("price", 0), "strategy_explanation": message_text}
                else:
                    error_text = await response.text()
                    print(f"[Langflow Client] Error: {response.status} - {error_text}")
                    return {"recommended_price": product_data.get("price", 0), "strategy_explanation": f"Langflow Error: {response.status}"}
    except Exception as e:
        print(f"[Langflow Client] Request failed: {e}")
        return {"recommended_price": product_data.get("price", 0), "strategy_explanation": "Langflow unavailable. Fallback to base price."}
