<div align="center">

![Klypup Header Banner](./screenshots/klypup_banner.png)

# 🧠 Klypup: Dynamic Pricing Intelligence Platform

### *Applied AI Decision-Support & Governance System*

> **An operational, multi-agent AI decision-support platform** that monitors market conditions, predicts demand elasticity, optimizes inventory yield, generates explainable pricing recommendations, and enforces a strict human-in-the-loop governance workflow.

<br/>

[![Vercel Deployment](https://img.shields.io/badge/%F0%9F%9A%80_Live_Demo-Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://dynamic-pricing-intelligence-platfo.vercel.app/login)
[![GitHub Repository](https://img.shields.io/badge/%E2%AD%90_GitHub-Repository-0f172a?style=for-the-badge&logo=github)](https://github.com/parthTyagi-tech/dynamic-pricing-intelligence-platform.git)

<br/>

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=flat-square&logo=flask&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=flat-square&logo=postgresql&logoColor=white)
![Docker Compose](https://img.shields.io/badge/Docker_Compose-Supported-2496ED?style=flat-square&logo=docker&logoColor=white)
![Llama-3.3-70b](https://img.shields.io/badge/LLM-Llama_3.3_70b_/_GPT--4o--mini-d97706?style=flat-square)
![JWT](https://img.shields.io/badge/JWT-Auth_Tenant_Isolation-000000?style=flat-square&logo=jsonwebtokens)

<br/>

> ⚠️ **This is not a chatbot.** It is a structured AI decision system — five specialized agents collaborate asynchronously, produce a confidence-scored recommendation with full rationale, and route it through a human approval workflow before any price change executes.

</div>

---

## 📋 Table of Contents

- [The Business Problem](#-the-business-problem)
- [Key Value Propositions](#-key-value-propositions)
- [System Architecture & Data Flows](#-system-architecture--data-flows)
- [Autonomous Multi-Agent Brain](#-autonomous-multi-agent-brain)
- [Human-in-the-Loop Governance](#-human-in-the-loop-governance)
- [LLM Observability & Cost Telemetry](#-llm-observability--cost-telemetry)
- [Conversational Command Console](#-conversational-command-console)
- [Price Elasticity A/B Testing](#-price-elasticity-ab-testing)
- [Visual Tour & Interactive Showcase](#-visual-tour--interactive-showcase)
- [Database Schema & Relational Integrity](#-database-schema--relational-integrity)
- [API Sandbox & Payload Catalog](#-api-sandbox--payload-catalog)
- [Quick Start Guide](#-quick-start-guide)
- [Engineering Decisions & Tradeoffs](#-engineering-decisions--tradeoffs)
- [Production Roadmap](#-production-roadmap)

---

## 🔴 The Business Problem

Mid-sized e-commerce companies managing 500+ SKUs typically reprice products manually on a weekly spreadsheet cycle. This lag generates severe operational friction and financial loss:

| Problem | Quantified Impact | Platform Resolution |
|---|---|---|
| **Lagging Competitor Adjustments** | **8–12% estimated revenue leakage** due to delayed or missed responses to market pressure. | **Market Intelligence Agent** monitors competitor feeds in real-time, instantly adjusting pricing bands. |
| **Static Pricing During Demand Surges** | Missed high-margin capture during seasonal and viral traffic spikes. | **Demand Forecast Agent** models elasticity & velocity signals, shifting to premium pricing postures dynamically. |
| **Inflexible Inventory Markdowns** | Overstocking forces deep, uncoordinated clearance markdowns, eroding net margins. | **Inventory Cost Agent** monitors inventory health and reorder thresholds, initiating gradual discounts. |
| **Operational Labor Sinks** | **70%+ of pricing analyst time** spent copy-pasting data, not making strategic decisions. | Automated multi-agent context aggregation surfaces complete explanations, reducing decision time from hours to seconds. |

---

## 💡 Key Value Propositions

- **🤖 Asynchronous Multi-Agent Engine**: Chains 5 specialized Pydantic-validated agents in parallel (`asyncio.gather`) to synthesize pricing recommendations based on competitor positions, inventory levels, category velocity, and strict compliance rules.
- **🛡️ Enterprise Multi-Tenancy**: Data isolation is enforced at the database query layer. The tenant `org_id` is extracted strictly from verified JWT claims, never from client-side request parameters.
- **👥 Role-Based Access Control**: Route decorators enforce role restrictions (`admin` vs. `analyst`). Analysts review and modify prices, while admins configure organizational compliance thresholds and margin floors.
- **📊 Real-time LLM Observability**: A built-in telemetry dashboard tracks LLM token counts, latencies, success rates, and real-time operational costs in USD.
- **💬 Conversational Command Console**: An interactive chatbot lets users query products, run multi-agent analyses, and approve pending pricing updates via natural language.
- **🧪 Price Elasticity A/B Testing**: Users can spin up A/B experiments for any SKU to compare control (A) vs. variant (B) revenue performance under price elasticity simulations.

---

## 🏗️ System Architecture & Data Flows

### High-Level Topology

```mermaid
graph TB
    subgraph Client["🖥️ Client — Vercel"]
        UI[React 18 SPA<br/>Vite · Framer Motion]
        Axios[Axios Interceptor<br/>JWT Authorization]
    end

    subgraph API["⚙️ Flask API Gateway — Render"]
        MW[JWT Middleware & RBAC Decorators]
        BP_AUTH[Auth Blueprint]
        BP_PROD[Products Blueprint]
        BP_REC[Recommendations Blueprint]
        BP_APR[Approvals Blueprint]
        BP_OBS[Observability Blueprint]
        BP_AB[A/B Test Blueprint]
        
        SVC[Service Layer<br/>Transactional Business Logic]
        ORCH[PricingOrchestrator<br/>Async multi-agent engine]
    end

    subgraph AI["🧠 AI & LLM Interface"]
        Groq[Groq / Llama-3.3-70b]
        OpenAI[OpenAI / GPT-4o-mini]
    end

    subgraph Mock["📊 Mock Data Providers"]
        M_COMP[Competitor Price Feed]
        M_DEM[Demand & Seasonality Signals]
        M_ECOM[E-Commerce API Executor]
    end

    subgraph DB["🗄️ Database — Render PostgreSQL"]
        PG[(PostgreSQL 15)]
    end

    UI -->|HTTPS REST + Bearer JWT| MW
    MW --> BP_AUTH & BP_PROD & BP_REC & BP_APR & BP_OBS & BP_AB
    BP_REC --> ORCH
    ORCH -->|asyncio.gather| Groq & OpenAI
    ORCH --> M_COMP & M_DEM
    BP_APR --> M_ECOM
    BP_AUTH & BP_PROD & BP_REC & BP_APR & BP_OBS & BP_AB --> SVC
    SVC -->|SQLAlchemy ORM| PG
```

### Request Lifecycle: Pricing Recommendation Run

The diagram below details the sequence of the pricing recommendation workflow, illustrating how the orchestrator triggers parallel agent reasoning, processes rules, checks compliance, and logs operational costs:

```mermaid
sequenceDiagram
    autonumber
    actor Analyst as Pricing Analyst
    participant FE as React Frontend
    participant GW as Flask API Gateway
    participant ORCH as PricingOrchestrator
    participant MOCK as Mock Data Sources
    participant LLM as Groq / OpenAI API
    participant COMP as Compliance Agent
    participant DB as PostgreSQL

    Analyst->HFE: Click "Generate Recommendation" (SKU 42)
    FE->>GW: POST /api/recommendations/ {product_id: 42} (with JWT)
    Note over GW: Extract org_id from verified JWT claims
    GW->>DB: Fetch product, inventory, and active PricingRule
    DB-->>GW: Product & Rule context
    GW->>ORCH: run(product, rules)
    
    par Ingest Competitor Data
        ORCH->>MOCK: fetch_competitor_prices(sku)
        MOCK-->>ORCH: Competitor data array
    and Ingest Demand Signals
        ORCH->>MOCK: fetch_demand_signals(sku)
        MOCK-->>ORCH: Seasonal trend data
    end

    par Phase 1: Market Agent (Async)
        ORCH->>LLM: Ingests competitor prices -> outputs market signals
        LLM-->>ORCH: MarketSignal (pressure, band)
    and Phase 1: Demand Agent (Async)
        ORCH->>LLM: Ingests demand velocity -> outputs elasticity
        LLM-->>ORCH: DemandSignal (trend, elasticity)
    and Phase 1: Inventory Agent (Async)
        ORCH->>LLM: Ingests inventory count -> outputs stocking pressure
        LLM-->>ORCH: InventorySignal (health, stockout eta)
    end

    Note over ORCH: Calculate LLM Token & Cost Telemetry
    ORCH->>DB: Write row to AI Call Log (cost, tokens, latency)

    Note over ORCH: Phase 2: Synthesis
    ORCH->>LLM: PricingStrategyAgent(synthesize upstream signals)
    LLM-->>ORCH: Raw RecommendationResult (price, confidence, rationale)

    Note over ORCH: Phase 3: Governance Check
    ORCH->>COMP: Check against margin floors & hard business constraints
    alt Violates margin floor
        COMP->>COMP: Adjust suggested price to compliant minimum
    end
    COMP-->>ORCH: Compliant Pricing Recommendation

    Note over ORCH: Phase 4: Route Decision
    alt Confidence >= Org Threshold AND Compliant
        ORCH->>ORCH: Set status to auto_execute
        ORCH->>MOCK: Call e-commerce API (update price storefront)
    else Confidence < Org Threshold
        ORCH->>ORCH: Set status to pending (routes to review queue)
    end

    ORCH->>DB: INSERT pricing_recommendations (state, signals, prices)
    DB-->>GW: Saved recommendation record
    GW-->>FE: 201 Created + Payload
    FE-->>Analyst: Render explainability panel & signals cards
```

---

## 🧠 Autonomous Multi-Agent Brain

Rather than relying on a single prompt template, the core pricing engine decouples analysis into five isolated agent modules, running Phase 1 concurrently using Python's `asyncio`.

```mermaid
graph TD
    CTX["📦 SKU Context & Org Rules"] -->|asyncio.gather| AGENTS
    
    subgraph AGENTS["Phase 1: Specialist Analysis (Parallel)"]
        MA["🌐 Market Intelligence Agent<br/>─<br/>Ingests competitor feeds<br/>Outputs: market_signal, pressure_score"]
        DA["📉 Demand Forecast Agent<br/>─<br/>Ingests category velocities<br/>Outputs: demand_trend, elasticity_score"]
        IA["📦 Inventory & Cost Agent<br/>─<br/>Checks COGS & warehouse logs<br/>Outputs: stockout_days, inventory_health"]
    end

    MA & DA & IA -->|Pydantic Validated Signals| PSA
    
    subgraph PSA["Phase 2: Strategy Synthesis"]
        Strategy["🎯 Pricing Strategy Agent<br/>─<br/>Synthesizes upstream signals<br/>Outputs: proposed_price, confidence_score"]
    end

    Strategy --> COMP
    
    subgraph COMP["Phase 3: Compliance & Execution"]
        Compliance["🛡️ Compliance Agent<br/>─<br/>Enforces margin floors & threshold rules<br/>Outputs: compliant_price, execution_route"]
    end

    Compliance -->|Above Threshold & Compliant| AUTO["⚡ Auto-Execute Price Update"]
    Compliance -->|Below Threshold / Margin Risk| QUEUE["⏳ Queue for Human Review"]
```

### Agent I/O Validation Schemas

To prevent agentic hallucinations or formatting drifts from breaking downstream agents, each agent communicates using strict, typed **Pydantic Schemas**. If a validation schema fails, the orchestrator catches the exception, logs it, and falls back to a low-confidence default signal instead of crashing.

<details>
<summary>🔍 View Pydantic Data Contract Schemas</summary>

```python
from pydantic import BaseModel, Field
from typing import Literal, Tuple, Dict, Any

class MarketSignal(BaseModel):
    signal_type: Literal["below_market", "at_market", "above_market"]
    price_band: Tuple[float, float] = Field(..., description="Min and max competitor prices")
    pressure_score: float = Field(..., ge=0.0, le=1.0)
    competitor_count: int
    confidence: float = Field(..., ge=0.0, le=1.0)

class DemandSignal(BaseModel):
    trend: Literal["increasing", "stable", "decreasing"]
    velocity_score: float = Field(..., ge=0.0, le=1.0)
    seasonality_factor: float
    confidence: float = Field(..., ge=0.0, le=1.0)

class InventorySignal(BaseModel):
    health: Literal["overstocked", "healthy", "tightening", "critical"]
    days_of_supply: int
    margin_floor: float
    constraint_flag: bool
    confidence: float = Field(..., ge=0.0, le=1.0)

class PricingRecommendationResult(BaseModel):
    recommended_price: float
    confidence_score: float
    strategy: Literal["liquidation", "exploit_monopoly", "clearance", "premium", "penetration", "maintain", "competitive"]
    rationale: str
    projected_volume_increase_pct: float
    projected_monthly_profit_lift: float
```

</details>

### Confidence Score Calculation

The final recommendation carries a composite confidence score, formulated as a weighted matrix based on agent domain weights:

$$\text{Confidence Score} = (C_M \times 0.35) + (C_D \times 0.35) + (C_I \times 0.30)$$

Where:
- $C_M$: Market Intelligence Agent confidence score
- $C_D$: Demand Forecast Agent confidence score
- $C_I$: Inventory & Cost Agent confidence score

*If the composite confidence score is $\ge$ the organization's config threshold, the Execution Agent routes the price update to auto-execution. Otherwise, it routes it to the human approval queue.*

---

## 👥 Human-in-the-Loop Governance

No AI model can modify live store prices unchecked. Recommendations that fall below the organization's threshold are held in a pending state until a reviewer intervenes.

```mermaid
stateDiagram-v2
    [*] --> Pending: Confidence < Threshold
    [*] --> AutoExecuted: Confidence >= Threshold & Compliant
    
    Pending --> Approved: Analyst accepts AI price
    Pending --> Modified: Analyst overrides price manually
    Pending --> Rejected: Analyst dismisses recommendation
    
    AutoExecuted --> PriceUpdated: Webhook success
    Approved --> PriceUpdated: DB transaction commits
    Modified --> PriceUpdated: Override price applied
    
    PriceUpdated --> AuditLogged: Write ledger record
    Rejected --> AuditLogged: Log rejection reason
    
    AuditLogged --> [*]
```

### Action Ledger Table

When analysts act in the approval queue, the database enforces transactional integrity across three actions:

| Action | Storefront Price Update | Audit Ledger Fields | Required Fields |
|---|---|---|---|
| **Approve** | Updates to AI Recommended Price. | `price_before`, `price_after`, `actor_id`, `recomm_id` | *None* |
| **Modify & Approve** | Updates to User Override Price. | `price_before`, `price_after` (applied), `recomm_price` (AI suggested), `actor_id` | `applied_price`, override note |
| **Reject** | Retains original price. | `action` (rejected), `actor_id`, `notes` (reason for rejection) | Rejection reason |

---

## 📊 LLM Observability & Cost Telemetry

Every agent call is tracked by a central database logger (`AICallLog`). This telemetry is displayed to administrators through a dedicated **Observability Dashboard** featuring real-time charts and summary metrics:

```
[Total LLM Cost: $0.1420] ── [Total Calls: 24] ── [Avg Latency: 1240 ms] ── [Success Rate: 100%]
```

- **Cost Analysis by Agent**: Breakdown of input/output token counts mapped to USD pricing models.
- **Model Distribution**: Tracks execution metrics between Llama 3.3 and GPT-4o-mini.
- **SVG Latency Sparklines**: Real-time canvas charts rendering latency variances in milliseconds over the last 30 requests.
- **Token Leakage Alerting**: Highlights failing or unusually high-cost calls for debugging.

---

## 💬 Conversational Command Console

The platform includes an agentic chat assistant blueprint (`/api/chatbot/chat`). It acts as a natural language CLI, executing commands securely through regex-based classification and prompt routing:

* **Triggering Analyses**: `"analyse product Sony WH-1000XM5"` or `"run pricing for SKU-902"` triggers the 5-agent pipeline, returning a structured markdown report of the consensus.
* **Inspecting Products**: `"price of Apple iPad"` pulls COGS, stock levels, margins, and active recommendation badges.
* **Workflow Approvals**: `"approve the recommendation for SKU-902"` performs the DB transaction, updating the storefront price.
* **Explanation Requests**: `"explain why the suggested price for iPhone is $899"` displays the agent breakdown.

---

## 🧪 Price Elasticity A/B Testing

Before committing to a permanent price increase, teams can launch A/B testing campaigns directly on the SKU details panel:

1. **Test Setup**: Define a control price (Branch A) and a variant price (Branch B).
2. **Elasticity Simulation**: A randomized sales generation script simulates checkout behavior against a standard price elasticity factor:
   
$$\text{Expected Sales}_B = \text{Sales}_A \times \left(1 - \left(\frac{P_B - P_A}{P_A}\right) \times \epsilon \right)$$

*Where $\epsilon = 1.5$ (represents the coefficient of price elasticity of demand).*

3. **Autocompletion**: Once the simulation completes, the system determines the winning branch based on maximum revenue generated and automatically sets the storefront price to the winner.

---

## 📸 Visual Tour & Interactive Showcase

### 1. Product Catalog Dashboard
A detailed overview of the inventory catalog. Highlights SKUs, current prices, margins, stock levels, and live recommendation status badges.
![Product Catalog Dashboard](./screenshots/dashboard-catalog.png)

---

### 2. AI Pricing Execution & Running Log
Watch the multi-agent pipeline trigger, fetching competitor data, executing parallel reasoning, and surfacing consensus details.
![AI Recommendation Generation](./screenshots/recommendation-generation.png)

---

### 3. Agent Signal Explainability Panel
Open a recommendation to see exactly how each agent reasoned, their relative confidence weights, and the original data sources behind the decision.
![Explainability Panel](./screenshots/explainability-panel.png)

---

### 4. Human Approval Queue
Manager view containing pending decisions. Allows analysts to approve, reject with a reason, or modify the final applied price.
![Approval Queue](./screenshots/approval-queue.png)

---

### 5. Observability Telemetry & Token Logs
Monitors API call counts, response latencies, and total accumulated cost in USD across all active LLM operations.
![Audit History](./screenshots/audit-history.png)

---

## 🗄️ Database Schema & Relational Integrity

The relational schema is configured to maintain strict ACID constraints. If an approval succeeds but the subsequent audit log write fails, the entire transaction rolls back.

```mermaid
erDiagram
    ORGANIZATIONS {
        string id PK
        string name
        float confidence_threshold
        float margin_floor_default
        timestamp created_at
    }

    USERS {
        string id PK
        string name
        string email UK
        string password_hash
        string role "admin | analyst"
        string organization_id FK
        timestamp created_at
    }

    PRODUCTS {
        string id PK
        string sku UK
        string name
        string category
        float current_price
        float cost_price
        float margin_floor
        int inventory_quantity
        string recommendation_status "pending | approved | rejected"
        string organization_id FK
    }

    PRICING_RECOMMENDATIONS {
        string id PK
        float recommended_price
        float confidence_score
        string status "pending | approved | rejected"
        text rationale
        jsonb agent_analysis "stores detailed signals"
        string product_id FK
        string organization_id FK
        timestamp created_at
    }

    AUDIT_LOGS {
        string id PK
        string action
        string entity_type
        string entity_id
        json extra_metadata
        string user_id FK
        string organization_id FK
        timestamp timestamp
    }

    AB_TESTS {
        string id PK
        float price_a
        float price_b
        int sales_a
        int sales_b
        float revenue_a
        float revenue_b
        string status "active | completed"
        string winner "A | B"
        string product_id FK
        string organization_id FK
        timestamp created_at
    }

    AI_CALL_LOGS {
        int id PK
        string agent_name
        string model_name
        int prompt_tokens
        int completion_tokens
        int total_tokens
        int latency_ms
        float cost
        string status
        string user_id FK
        string organization_id FK
        timestamp timestamp
    }

    ORGANIZATIONS ||--o{ USERS : "has many"
    ORGANIZATIONS ||--o{ PRODUCTS : "owns"
    ORGANIZATIONS ||--o{ PRICING_RECOMMENDATIONS : "scopes"
    ORGANIZATIONS ||--o{ AUDIT_LOGS : "logs"
    ORGANIZATIONS ||--o{ AB_TESTS : "runs"
    ORGANIZATIONS ||--o{ AI_CALL_LOGS : "monitors"
    
    USERS ||--o{ AUDIT_LOGS : "performs"
    PRODUCTS ||--o{ PRICING_RECOMMENDATIONS : "receives"
    PRODUCTS ||--o{ AB_TESTS : "tests"
```

---

## 📡 API Sandbox & Payload Catalog

All tenant endpoints require a Bearer token: `Authorization: Bearer <jwt_token>`.

### Endpoint Directory

| Blueprint | Method | Path | Auth | Role | Action |
|---|---|---|---|---|---|
| **Auth** | POST | `/api/auth/register` | None | - | Registers new org & admin user |
| | POST | `/api/auth/login` | None | - | Issues JWT containing role/tenant claims |
| **Products**| GET | `/api/products/` | JWT | Analyst+ | Lists products (isolated by tenant) |
| | POST | `/api/products/` | JWT | Admin | Inserts new catalog SKU |
| **AI Pricing**| POST | `/api/recommendations/` | JWT | Analyst+ | Triggers multi-agent pricing orchestration |
| | GET | `/api/recommendations/:id` | JWT | Analyst+ | Fetches explainability signals JSON |
| **Approvals**| GET | `/api/approvals/pending`| JWT | Analyst+ | Gets queue of pending recommendations |
| | POST | `/api/approvals/:id/approve`| JWT | Analyst+ | Approves suggested price |
| | POST | `/api/approvals/:id/modify`| JWT | Analyst+ | Overrides suggested price |
| **Telemetry**| GET | `/api/observability/stats`| JWT | Admin | Returns aggregate token, cost, latency lists |
| **A/B Test** | POST | `/api/ab-test/start/:id` | JWT | Analyst+ | Initializes A/B variants for SKU |
| | POST | `/api/ab-test/simulate/:id`| JWT | Analyst+ | Simulates elasticity & closes experiment |

### Payloads Showcase

<details>
<summary>📲 POST /api/recommendations/ (Trigger Run)</summary>

```http
POST /api/recommendations/
Authorization: Bearer eyJhbGciOi...
Content-Type: application/json

{
  "product_id": "8f87b8d4-53c2-4cf4-a5e2-04e40292723c"
}
```

```json
{
  "id": "c1a6b0c2-55db-49de-8409-d7b322fa1e19",
  "product_id": "8f87b8d4-53c2-4cf4-a5e2-04e40292723c",
  "recommended_price": 249.99,
  "confidence_score": 0.88,
  "status": "pending",
  "rationale": "Competitor pricing average dropped to $245.00. Inventory is healthy (24 days of supply). High demand category support justifies a moderate competitive drop to $249.99 while maintaining a 28% margin floor. Confidence score (88%) is below your org threshold (90%) - routed to review queue.",
  "agent_signals": {
    "market_agent": {
      "signal_type": "above_market",
      "price_band": [239.99, 259.99],
      "pressure_score": 0.65,
      "confidence": 0.90
    },
    "demand_agent": {
      "trend": "increasing",
      "velocity_score": 0.82,
      "confidence": 0.85
    },
    "inventory_agent": {
      "health": "healthy",
      "days_of_supply": 24,
      "margin_floor": 180.00,
      "confidence": 0.92
    }
  }
}
```

</details>

<details>
<summary>📲 POST /api/approvals/:id/modify (Override Price)</summary>

```http
POST /api/approvals/c1a6b0c2-55db-49de-8409-d7b322fa1e19/modify
Authorization: Bearer eyJhbGciOi...
Content-Type: application/json

{
  "applied_price": 254.99,
  "notes": "Overriding AI suggested drop to maintain higher gross margin target during active promotion."
}
```

```json
{
  "success": true,
  "decision": "modified",
  "ai_recommended_price": 249.99,
  "applied_price": 254.99,
  "ecommerce_api_status": "success",
  "audit_log_id": "e22a90f1-081e-4cb8-8c11-094ee94bb100"
}
```

</details>

---

## 🚀 Quick Start Guide

### Docker Compose (1-Command Run)

Make sure Docker and Docker Compose are installed. Run the following command from the project root:

```bash
docker compose up --build
```

- **Frontend Interface**: [http://localhost:80](http://localhost:80) (mapped from container port 80)
- **Backend API Gateway**: [http://localhost:5000](http://localhost:5000)
- **Local PostgreSQL**: `localhost:5432`

---

### Manual Setup (Step-by-Step)

If you prefer running without Docker, follow these instructions:

#### 1. Configure the Environment
Copy `.env.example` templates in both `backend/` and `frontend/` folders:

* **Backend Environment (`backend/.env`)**:
  ```env
  FLASK_APP=run.py
  FLASK_ENV=development
  DATABASE_URL=postgresql://klypup:klypup_secure_password@localhost:5432/klypup
  JWT_SECRET_KEY=generate_your_jwt_secret_hex
  SECRET_KEY=generate_your_flask_secret_hex
  AI_PROVIDER=groq # Options: 'groq' | 'openai'
  GROQ_API_KEY=gsk_...
  OPENAI_API_KEY=sk_proj_...
  ```

* **Frontend Environment (`frontend/.env`)**:
  ```env
  VITE_API_URL=http://localhost:5000/api
  ```

#### 2. Install & Start Backend
```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

# Run migrations & seed catalog databases
flask db upgrade
python seed.py

# Launch local server
flask run --port 5000
```

#### 3. Install & Start Frontend
```bash
cd frontend
npm install
npm run dev
# Vite runs local server at http://localhost:5173
```

---

### Demo Organization Credentials

The seeding script (`python seed.py`) registers two isolated organizations. You can log in with these roles to test multi-tenant boundaries:

**🏢 Organization A — Acme Electronics**
* **Admin Role**: `admin@acme.com` / `acme-admin-2024`
* **Analyst Role**: `analyst@acme.com` / `acme-analyst-2024`

**🏢 Organization B — Bravo Retail**
* **Admin Role**: `admin@bravo.com` / `bravo-admin-2024`
* **Analyst Role**: `analyst@bravo.com` / `bravo-analyst-2024`

---

## 📝 Engineering Decisions & Tradeoffs

### 1. Shared Schema with Tenant ID Column
* **Decision**: Selected a shared-database, shared-schema architecture using an `organization_id` index filter on every query.
* **Tradeoff**: While a schema-per-tenant pattern provides stronger database-level isolation, it introduces migration scaling complexity. We mitigated this by enforcing the tenant extraction exclusively on verified JWT claims in middleware, making cross-tenant data leaks structurally impossible.

### 2. PostgreSQL Relational Integrity vs. Document Store
* **Decision**: PostgreSQL was selected over MongoDB.
* **Tradeoff**: Relational tables enforce ACID transactions during the multi-step approval workflow. The flexible, unstructured output of LLM agent signals is stored in a `JSONB` column type on the recommendations table, giving us the benefit of a document store without losing foreign key constraints.

### 3. Asynchronous Python Orchestrator inside a WSGI Flask App
* **Decision**: The backend runs the three Phase 1 agents in parallel using Python's `asyncio`.
* **Tradeoff**: Flask is traditionally synchronous. We integrated `asyncio.run` inside the route context to fire concurrent tasks, reducing total API response latency from ~9 seconds to ~3 seconds. For true production scales, we plan to delegate these tasks to Celery workers with a Redis broker, enabling the client to poll via SSE.

---

## 🎯 Production Roadmap

Our execution milestones for scaling the platform:

- [ ] **Task Delegation (Celery + Redis)**: Offload LLM agent tasks to Celery worker threads. Enable immediate `202 Accepted` status returns, allowing the React client to poll or connect via Server-Sent Events (SSE) for real-time progress cards.
- [ ] **Embeddings Search (pgvector)**: Convert historical pricing actions, override rationales, and product tags to vector embeddings. Ingest them as few-shot context templates into the Pricing Strategy Agent to ensure consistent recommendations.
- [ ] **Scraping Worker Integration**: Connect real competitor price scraping pipelines (e.g. Scrapy, BrightData) to periodically update the catalog's competitive signals.
- [ ] **Silent Token Refreshing**: Implement JWT refresh token rotation with a sliding window, preventing analysts from getting logged out mid-session.
- [ ] **Comprehensive Test Coverage**: Write a suite of `pytest` unit/integration tests targeting the tenant isolation filters and contract schema validation routines.

---

<div align="center">

*Multi-Agent Orchestration · Enterprise Tenant Isolation · Strict Governance*

</div>
