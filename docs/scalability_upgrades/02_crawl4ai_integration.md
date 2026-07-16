# Phase 2: Crawl4AI Integration Blueprint

## Objective
Replace the mock competitor pricing feed with a live, real-time scraping service using Crawl4AI to ingest live pricing data directly into the pricing orchestrator.

## Changes Required

### 1. `backend/services/competitor_feed.py` (New File)
*   **Action:** Create a new service wrapper around `crawl4ai`.
*   **Change:**
```python
import asyncio
from crawl4ai import AsyncWebCrawler

async def fetch_real_competitor_price(product_url: str):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=product_url)
        # Use LLM/regex to extract price from result.markdown
        return extract_price(result.markdown)
```

### 2. `backend/orchestrator/PricingOrchestrator.py`
*   **Action:** Remove the `mock_fetch_competitor_prices` call.
*   **Change:** Inject the new Crawl4AI service. When a pricing recommendation is requested, the system will actively hit the competitor's URL, parse the markdown, and feed the *live* price into the LLM.

### 3. Docker Infrastructure
*   **Action:** Depending on deployment, Crawl4AI may need Playwright browsers installed in the backend Dockerfile.
*   **Change:** Add `playwright install chromium` to the `backend/Dockerfile`.

## Expected Outcome
The pricing recommendations will switch from being based on static/dummy data to utilizing live, up-to-the-minute market signals, making the platform genuinely capable of beating competitor price changes instantly.
