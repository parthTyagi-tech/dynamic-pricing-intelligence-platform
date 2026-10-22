# Klypup Model Context Protocol (MCP) Server Specification

An enterprise-grade, production-deployed **Model Context Protocol (MCP)** server built with Python's official `mcp` SDK (`FastMCP`). 

This server exposes Klypup's 18 marketplace scrapers, multi-agent pricing swarm, and atomic Compare-And-Swap (CAS) price ledger to external AI clients (Cursor, Claude Desktop, Antigravity, Windsurf).

---

## 1. System Architecture

```
┌────────────────────────────────────────────────────────┐
│                   External AI Hosts                    │
│      Cursor IDE  │  Claude Desktop  │  Custom LLM      │
└───────────────────────────┬────────────────────────────┘
                            │  HTTPS / Server-Sent Events (SSE)
                            │  Authorization: Bearer <API_KEY>
                            │  X-Organization-Id / X-User-Id
                            ▼
┌────────────────────────────────────────────────────────┐
│              FastMCP Server (Render Cloud)             │
│  File: backend/app/mcp/server.py                       │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Starlette Auth Middleware (Bearer Token)         │  │
│  │ Unauthenticated /health endpoint                 │  │
│  │ Request Tenant Context Injection (ContextVars)   │  │
│  └────────────────────────┬─────────────────────────┘  │
│                           │ Scoped Context Session     │
│                           │ redirect_stdout(stderr)    │
│                           ▼                            │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 7 Tools    │ 4 Resources   │ 2 Workflows/Prompts │  │
│  └────────────────────────┬─────────────────────────┘  │
└───────────────────────────┼────────────────────────────┘
                            │ In-Process DB Session
                            ▼
┌────────────────────────────────────────────────────────┐
│               Core Klypup Engine & Ledger              │
│  • 18 Marketplace Scraper Sensors (Amazon, Blinkit...) │
│  • Supervisor & Aggregator Multi-Agent Swarm           │
│  • SEC-9 Margin Floor ($P \ge Cost + Margin$)          │
│  • SEC-10 Sanity Bound ($\pm 50\%$)                    │
│  • Optimistic CAS Price Ledger & Anti-Replay Rollback  │
│  • PostgreSQL DB (Supabase IPv4 Pooler)                │
└────────────────────────────────────────────────────────┘
```

---

## 2. Server Deployment & Transport Modes

The server supports two distinct transports configured via CLI flags:

### A. Cloud Production Mode (SSE over HTTP)
* **Command:** `python backend/app/mcp/server.py --transport sse --host 0.0.0.0 --port $PORT`
* **Live Render Endpoint:** `https://dynamic-pricing-intelligence-platform-1.onrender.com/sse`
* **Health Check Probe:** `https://dynamic-pricing-intelligence-platform-1.onrender.com/health` (Returns `200 OK`, unauthenticated for cloud health checkers).
* **Protocol:**
  * `GET /sse`: Establishes the Server-Sent Events event stream.
  * `POST /messages?session_id=<id>`: Submits JSON-RPC 2.0 tool/resource invocations.

### B. Local Subprocess Mode (`stdio`)
* **Command:** `python backend/app/mcp/server.py --transport stdio`
* Communicates directly through `sys.stdin` and `sys.stdout` via standard JSON-RPC framing.
* Ideal for local CLI agents and local desktop runners.

---

## 3. Security, Authentication & Multi-Tenancy

### Bearer Authentication
When deployed with `KLYPUP_MCP_API_KEY` set in the environment, all requests to `/sse` and `/messages` require an HTTP header:
```http
Authorization: Bearer <KLYPUP_MCP_API_KEY>
```

### Multi-Tenant Isolation (`SEC-1` & `SEC-2`)
Every query and mutation strictly belongs to an authenticated organization:
1. **Per-Request Headers:** The client can supply `X-Organization-Id` and `X-User-Id` headers.
2. **Environment Variables:** Falls back to `KLYPUP_MCP_ORG_ID` and `KLYPUP_MCP_USER_ID`.
3. **Database Fallback:** Dynamically resolves the primary seeded active tenant and admin.
4. **Tenant Sandboxing:** Invocations attempting to query or modify a SKU belonging to another tenant raise a hard `SEC-1` violation error.

### Stream Pollution Protection
Scraping engines and third-party libraries often print debug logs to standard output. In `stdio` mode, unformatted text breaks the JSON-RPC parser.
* Logging is bound strictly to `sys.stderr`.
* Every tool and resource executes inside `contextlib.redirect_stdout(sys.stderr)`.

### Background Worker Process Isolation
The Flask application is initialized using `create_app(start_worker=False)`. This ensures that MCP worker threads do not accidentally launch background Celery or scheduler workers.

---

## 4. The 7 MCP Tools

### `1. scrape_marketplace`
Runs live web scraping against any of Klypup's 18 supported e-commerce marketplaces.
* **Arguments:**
  * `platform` *(str, required)*: Marketplace name (e.g., `amazon`, `flipkart`, `blinkit`, `myntra`, `ajio`, `nykaa`, `bigbasket`, `zepto`, `meesho`, etc.).
  * `product_name` *(str, required)*: Search query / title.
  * `brand` *(str, optional)*: Product brand name.
  * `barcode` *(str, optional)*: UPC/EAN barcode.
  * `catalog_price` *(float, optional)*: Baseline catalog price for variance checks.
* **Returns:**
  ```json
  {
    "platform": "amazon",
    "status": "success",
    "price": 1499.0,
    "mrp": 1999.0,
    "match_score": 0.94,
    "tier_used": "playwright_stealth",
    "product_url": "https://...",
    "in_stock": true,
    "latency_ms": 1420
  }
  ```

### `2. scrape_category_swarm`
Fans out parallel scraping across all platforms relevant to the product's category, cleans offers, and filters Median Absolute Deviation (MAD) statistical outliers.
* **Arguments:**
  * `product_id` *(str/int, required)*: UUID or SKU of the product.
  * `force_refresh` *(bool, optional)*: Bypasses the 20-minute cache if true.
* **Returns:**
  ```json
  {
    "sku": "SKU-PROD-101",
    "target_platforms": ["amazon", "flipkart", "croma"],
    "market_avg": 1485.50,
    "market_min": 1420.00,
    "market_max": 1550.00,
    "verified_count": 3,
    "valid_offers": [...],
    "discarded_outliers": 0
  }
  ```

### `3. run_full_pricing_swarm`
Executes the full multi-agent pricing workflow: checks 20-min idempotency, runs parallel scraping, debates between **Agent A (Margin Floor)** and **Agent B (Competitor Elasticity)**, verifies SEC-9/SEC-10 rules, and persists a `PricingRecommendation`.
* **Arguments:**
  * `product_id` *(str/int, required)*: UUID or SKU.
  * `force_refresh` *(bool, optional)*: If true, forces fresh scrape and reasoning run.
* **Returns:**
  ```json
  {
    "recommendation_id": "rec-uuid-1234",
    "sku": "SKU-PROD-101",
    "current_price": 1600.0,
    "cost_price": 1100.0,
    "recommended_price": 1450.0,
    "confidence_score": 0.88,
    "margin_floor_applied": false,
    "sanity_bound_flagged": false,
    "reasoning_text": "Undercutting Amazon competitor while preserving 24% gross margin.",
    "status": "pending"
  }
  ```

### `4. approve_or_reject_recommendation`
Human-in-the-loop decision endpoint for pricing recommendations.
* **Arguments:**
  * `recommendation_id` *(str, required)*: UUID of pending recommendation.
  * `action` *(str, required)*: Either `"approve"` or `"reject"`.
  * `reason` *(str, optional)*: Decision commentary.
* **Safety Mechanism:**
  * Uses **Compare-And-Swap (CAS)** against `expected_base_price`.
  * Enforces **SEC-9** Margin Floor ($P \ge \text{Cost} + \text{Margin}$) and **SEC-10** ($\pm 50\%$) boundaries.
  * Creates an immutable audit record and returns an `action_id`.
* **Returns:**
  ```json
  {
    "status": "approved",
    "action_id": "action-uuid-5678",
    "sku": "SKU-PROD-101",
    "old_price": 1600.0,
    "new_price": 1450.0,
    "history_id": 42,
    "audit_id": 108
  }
  ```

### `5. rollback_price_change`
Restores a product's price back to its prior value using the `action_id` from a previous approval.
* **Arguments:**
  * `action_id` *(str, required)*: UUID returned by `approve_or_reject_recommendation`.
* **Anti-Replay Guardrail:**
  * If the action has already been rolled back, it raises a strict error, preventing loops or corrupted pricing ledgers.
* **Returns:**
  ```json
  {
    "status": "rolled_back",
    "rollback_action_id": "rb-uuid-9999",
    "sku": "SKU-PROD-101",
    "previous_price": 1450.0,
    "restored_price": 1600.0
  }
  ```

### `6. check_or_reset_circuit_breakers`
Telemetry and maintenance interface for the 18 scraper circuit breakers.
* **Arguments:**
  * `reset` *(bool, optional)*: If `true`, resets failure counts and sets all states to `"closed"`.
  * `run_canaries` *(bool, optional)*: If `true`, executes active canary health probes across all platforms.
* **Returns:** Total platforms, current state of each platform, failure counters, and probe results.

### `7. simulate_price_elasticity`
Runs a non-mutating log-linear simulation testing revenue, volume, and profit under different price elasticity assumptions over a timeline (default 30 days).
* **Arguments:**
  * `product_id` *(str/int, required)*: UUID or SKU.
  * `elasticity` *(float, optional)*: Coefficient (default `-1.5`).
  * `days` *(int, optional)*: Projection horizon in days (default `30`).
* **Returns:** Projected revenue, projected profit, revenue lift %, and day-by-day simulated timeline.

---

## 5. The 4 MCP Resources

Resources allow LLMs to read live system state directly into their context window via standard URIs:

| Resource URI | Description | Output Format |
|---|---|---|
| `klypup://catalog/products` | Live product catalog for tenant: current price, cost price, stock, and computed margin floors. | JSON Array |
| `klypup://catalog/product/{sku}/history` | Complete price change audit trail and historical ledger for a specific SKU. | JSON Object |
| `klypup://scrapers/health` | Live circuit breaker status, error counters, backoff timers, and last scrape times for all 18 scrapers. | JSON Array |
| `klypup://recommendations/pending` | All pricing recommendations currently awaiting approval. | JSON Array |

---

## 6. The 2 MCP Prompts (Workflows)

Prompts are predefined prompt templates guiding external LLMs through complex operational procedures:

### `1. audit_sku_pricing(sku)`
Directs the AI to:
1. Fetch history from `klypup://catalog/product/{sku}/history`.
2. Run `run_full_pricing_swarm` on the SKU.
3. Compare Agent A (Margin Floor) vs Agent B (Competitor Elasticity).
4. Verify SEC-9 and SEC-10 guardrails.
5. Formulate an executive pricing recommendation memo.

### `2. diagnose_platform_sensor(platform)`
Directs the AI to:
1. Inspect health at `klypup://scrapers/health`.
2. Run a test probe scrape via `scrape_marketplace`.
3. Check match score, tier used, and latency budget compliance (< 15s).
4. Report scraper status (operational, degraded, or selector update required).

---

## 7. Connecting External AI Clients

### Cursor Configuration
Add to your project's `.cursor/mcp.json` or Global Cursor Settings:
```json
{
  "mcpServers": {
    "klypup": {
      "url": "https://dynamic-pricing-intelligence-platform-1.onrender.com/sse",
      "headers": {
        "Authorization": "Bearer <YOUR_KLYPUP_MCP_API_KEY>"
      }
    }
  }
}
```

### Claude Desktop Configuration
Add to `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):
```json
{
  "mcpServers": {
    "klypup": {
      "url": "https://dynamic-pricing-intelligence-platform-1.onrender.com/sse",
      "headers": {
        "Authorization": "Bearer <YOUR_KLYPUP_MCP_API_KEY>"
      }
    }
  }
}
```

### Testing with Python MCP SDK
```python
import asyncio
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

async def main():
    headers = {"Authorization": "Bearer YOUR_KLYPUP_MCP_API_KEY"}
    async with sse_client("https://dynamic-pricing-intelligence-platform-1.onrender.com/sse", headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List all tools
            tools = await session.list_tools()
            print(f"Discovered {len(tools.tools)} tools.")
            
            # Invoke a tool
            result = await session.call_tool("simulate_price_elasticity", {"product_id": "SKU-PROD-001"})
            print(result)

asyncio.run(main())
```
