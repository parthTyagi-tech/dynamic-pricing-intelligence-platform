# Phase 4: Browser Use Execution Blueprint

## Objective
Replace the `MockEcommerceAPI` executor with an autonomous web agent using `browser-use`. When a human analyst approves a price change in the UI, this agent will physically execute the change on a target e-commerce platform (e.g., Shopify) if no API is available.

## Changes Required

### 1. `backend/services/browser_executor.py` (New File)
*   **Action:** Create a script leveraging `browser-use`.
*   **Change:**
```python
from browser_use import Agent, Browser
from langchain_openai import ChatOpenAI

async def execute_price_change_in_browser(sku: str, new_price: float):
    agent = Agent(
        task=f"Go to shopify.com, log in, search for SKU {sku}, and change the price to {new_price}. Click save.",
        llm=ChatOpenAI(model="gpt-4o"),
        browser=Browser()
    )
    result = await agent.run()
    return result
```

### 2. `backend/blueprints/approvals.py`
*   **Action:** Hook the new script into the approval route.
*   **Change:** When the `/api/approvals/<id>/approve` route is hit, instead of just updating the local DB, trigger a Celery background task that spins up the `browser-use` agent to apply the change in the real world.

## Expected Outcome
The platform transforms from a purely advisory dashboard into a closed-loop system that can take autonomous physical action on legacy web portals that lack proper APIs.
