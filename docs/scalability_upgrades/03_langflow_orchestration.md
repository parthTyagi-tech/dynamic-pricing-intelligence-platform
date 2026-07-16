# Phase 3: Langflow / Dify Orchestration Blueprint

## Objective
Decouple the multi-agent logic (the 5 AI agents) from the hardcoded Python `PricingOrchestrator` and move it to a visually managed Langflow or Dify pipeline.

## Changes Required

### 1. Langflow Setup
*   **Action:** Spin up a Langflow instance via Docker.
*   **Change:** Recreate the 5 agents (Competitor Agent, Inventory Agent, Demand Agent, Compliance Agent, Summarizer) as a visual flow graph.

### 2. `backend/orchestrator/PricingOrchestrator.py`
*   **Action:** Delete the complex `asyncio.gather` code calling Groq/OpenAI directly.
*   **Change:** Replace it with a single REST API call to the Langflow webhook.
```python
import requests

def get_pricing_recommendation(context_data):
    response = requests.post(
        "http://langflow:7860/api/v1/run/pricing-flow", 
        json={"inputs": context_data}
    )
    return response.json()
```

## Expected Outcome
Non-engineers (like Data Scientists or Pricing Analysts) will be able to tweak the prompts and logic of the 5 agents visually in the Langflow UI without needing to submit PRs or redeploy the Flask backend. This massively accelerates prompt engineering iterations.
