<div align="center">

# 🧠 Klypup

### **Dynamic Pricing Intelligence Dashboard**

> *An Applied AI decision-support platform that orchestrates multi-agent intelligence to generate explainable, governance-ready pricing recommendations at scale.*

<br/>

[![Live Frontend](https://img.shields.io/badge/Frontend-Live%20Demo-22c55e?style=for-the-badge&logo=vercel&logoColor=white)](https://your-frontend-url.vercel.app)
[![API Backend](https://img.shields.io/badge/Backend-API%20Live-3b82f6?style=for-the-badge&logo=render&logoColor=white)](https://your-backend-url.onrender.com)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-0f172a?style=for-the-badge&logo=github&logoColor=white)](https://github.com/yourusername/klypup)
[![License](https://img.shields.io/badge/License-MIT-a855f7?style=for-the-badge)](LICENSE)

<br/>

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-000000?style=flat-square&logo=flask&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=flat-square&logo=postgresql&logoColor=white)
![Anthropic](https://img.shields.io/badge/Anthropic-Claude-d97706?style=flat-square&logo=anthropic&logoColor=white)
![JWT](https://img.shields.io/badge/JWT-Auth-000000?style=flat-square&logo=jsonwebtokens&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)

<br/>

> **Klypup** is not a chatbot. It is an **operational AI decision-support platform** — a multi-agent orchestration system that continuously analyzes market conditions, demand signals, and inventory states to produce confidence-scored, explainable pricing recommendations with full human approval workflows and enterprise-grade audit trails.

<br/>

---

</div>

## 📋 Table of Contents

- [The Business Problem](#-the-business-problem)
- [Solution Overview](#-solution-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Multi-Agent AI System](#-multi-agent-ai-system)
- [Human-in-the-Loop Workflow](#-human-in-the-loop-workflow)
- [Frontend Architecture](#-frontend-architecture)
- [Backend Architecture](#-backend-architecture)
- [Database Design](#-database-design)
- [Tech Stack](#-tech-stack)
- [Live Demo & Screenshots](#-live-demo--screenshots)
- [Installation & Setup](#-installation--setup)
- [API Documentation](#-api-documentation)
- [Security & Multi-Tenancy](#-security--multi-tenancy)
- [Scalability & Roadmap](#-scalability--roadmap)
- [Engineering Decisions & Tradeoffs](#-engineering-decisions--tradeoffs)
- [Conclusion](#-conclusion)

---

## 🔴 The Business Problem

Modern pricing is broken — not because teams lack data, but because they lack **orchestrated intelligence**.

### Why Static Pricing Fails

Traditional pricing systems operate on rigid, rule-based logic: fixed margins, periodic manual reviews, and reactive adjustments after market conditions have already shifted. This approach creates compounding inefficiencies:

| Problem | Business Impact |
|---|---|
| **Static rules can't adapt to real-time signals** | Lost revenue during demand surges; margin erosion during slowdowns |
| **Inventory-pricing disconnect** | Overstocked products stay full-price; understocked items get discounted |
| **No competitive signal integration** | Prices drift from market benchmarks without operational awareness |
| **Black-box AI recommendations** | Teams reject or blindly trust AI outputs — neither outcome is safe |
| **No governance layer** | Pricing changes bypass approval workflows, creating compliance and audit risk |
| **Siloed operational data** | Demand, inventory, and market data live in separate systems with no synthesis layer |

### The Real Cost

> Research consistently shows that a **1% improvement in pricing strategy translates to an average 8–11% improvement in operating profit** — making pricing intelligence one of the highest-leverage applied AI domains in enterprise operations.

The gap isn't data availability — it's **intelligent orchestration with explainability and human oversight**. That's the problem Klypup solves.

---

## 💡 Solution Overview

**Klypup** is a full-stack Applied AI platform that deploys a **coordinated multi-agent system** to generate dynamic, explainable, governance-ready pricing recommendations — with a structured human approval workflow at its core.

### How It Works

```
Market Data + Inventory State + Demand Signals
         ↓
  Multi-Agent AI Orchestration (4 specialized agents)
         ↓
  Confidence-Scored Recommendation + Rationale
         ↓
  Human Review Queue (Approval / Rejection)
         ↓
  Product Price Update + Immutable Audit Log
```

### What Makes Klypup Different

- **Not a chatbot.** Not a copilot. A structured **AI decision system** with defined inputs, outputs, and governance.
- **Explainability-first.** Every recommendation includes agent-level rationale, market signals, confidence scores, and human-readable justification.
- **Governance-native.** No AI recommendation modifies production data without human approval. The approval workflow is an architectural primitive, not an afterthought.
- **Multi-tenant isolation.** Each organization's data, recommendations, products, and audit history are fully isolated at the database and application layer.
- **Audit-complete.** Every decision, approval, rejection, and price change is logged immutably for compliance and operational review.

---

## ✨ Key Features

### 🤖 Multi-Agent AI System
A coordinated ensemble of four specialized AI agents — Market Intelligence, Demand Forecasting, Inventory Analysis, and Pricing Strategy — each contributing domain-specific signals that are synthesized into a unified recommendation. Agents are orchestrated sequentially with structured data handoff between layers.

### 📊 Dynamic Pricing Intelligence
Real-time pricing analysis that accounts for competitor positioning, demand elasticity, inventory levels, and strategic pricing objectives. Recommendations are generated per-product with full context visibility.

### 🔍 Explainability Dashboard
Every AI recommendation surfaces its reasoning: which agents contributed what signal, what the confidence score represents, and why this specific price was recommended. Built for trust, not opacity.

### ✅ Approval Workflow
A structured human-in-the-loop review system. All AI recommendations enter a **Pending** state before any product data is modified. Managers review, approve, or reject with optional commentary. Approved recommendations trigger automated product price updates.

### 📜 Audit History
Immutable, timestamped log of every pricing action: who reviewed, when, what decision was made, and what changed. Supports compliance, accountability, and operational post-mortems.

### 🔐 Role-Based Access Control (RBAC)
Differentiated access tiers — `admin`, `manager`, and `viewer` — control who can generate recommendations, approve workflows, view audit logs, and manage users.

### 🏢 Multi-Tenant Architecture
Organization-level data isolation ensures that Klypup operates safely as a shared platform. Every API call, database query, and recommendation is scoped to the authenticated organization.

### 📈 Real-Time Dashboard
A responsive analytics dashboard displaying current product portfolio, AI recommendation status, approval queue depth, and pricing performance metrics — all in a unified operational view.

### 🎯 AI Confidence Scoring
Each recommendation carries a normalized confidence score (0.0–1.0) derived from the agreement and signal strength across all contributing agents. Low-confidence recommendations are surfaced with appropriate visual indicators for heightened human scrutiny.

### 🌐 Market Intelligence
The Market Intelligence Agent analyzes competitive pricing, market positioning, and external demand signals to inform recommendations with external context.

### 📉 Demand Forecasting
The Demand Forecast Agent models historical sales velocity, trend direction, and seasonal signals to project forward-looking demand pressure — a critical input to optimal pricing strategy.

### 📦 Inventory Analysis
The Inventory Agent evaluates current stock levels, days-of-supply, and reorder signals to modulate pricing recommendations — driving higher prices when inventory is tight, clearance-adjusted prices when overstocked.

### 🖥️ Responsive UI
Built with React 18, the frontend adapts seamlessly across desktop and tablet viewports with a clean, data-dense operational aesthetic designed for business users, not consumers.

### 🔑 JWT Authentication
Stateless, secure JWT-based authentication with organization-scoped token payloads. Tokens carry role and tenant claims, enabling middleware-layer enforcement across all protected routes.

### 🚀 Deployment Infrastructure
Frontend deployed on **Vercel** with CI/CD integration. Backend deployed on **Render** with managed PostgreSQL. Fully environment-variable-driven configuration for deployment portability.

---

## 🏗️ System Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph Client["🖥️ Client Layer"]
        UI[React 18 SPA]
        Router[React Router v6]
        State[Local State + Context]
    end

    subgraph API["⚙️ API Layer — Flask"]
        Auth[Auth Blueprint]
        Products[Products Blueprint]
        Recs[Recommendations Blueprint]
        Approvals[Approvals Blueprint]
        Audit[Audit Blueprint]
        MW[JWT Middleware + RBAC Guard]
    end

    subgraph AI["🧠 AI Orchestration Layer"]
        Orch[Pricing Orchestrator]
        MA[Market Intelligence Agent]
        DA[Demand Forecast Agent]
        IA[Inventory Agent]
        PA[Pricing Strategy Agent]
    end

    subgraph Data["🗄️ Data Layer"]
        PG[(PostgreSQL)]
        ORM[SQLAlchemy ORM]
    end

    UI -->|HTTPS REST| MW
    MW --> Auth
    MW --> Products
    MW --> Recs
    MW --> Approvals
    MW --> Audit
    Recs --> Orch
    Orch --> MA
    Orch --> DA
    Orch --> IA
    MA --> PA
    DA --> PA
    IA --> PA
    PA --> Orch
    Orch -->|Structured Result| Recs
    API --> ORM
    ORM --> PG
```

### Request Lifecycle

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant F as React Frontend
    participant MW as Flask Middleware
    participant BP as Blueprint Handler
    participant SVC as Service Layer
    participant AI as AI Orchestrator
    participant DB as PostgreSQL

    U->>F: Trigger "Generate Recommendation"
    F->>MW: POST /api/recommendations/ + JWT
    MW->>MW: Validate JWT, Extract org_id + role
    MW->>BP: Route to Recommendations Blueprint
    BP->>SVC: Call RecommendationService
    SVC->>DB: Fetch product + inventory + history
    SVC->>AI: Invoke PricingOrchestrator(context)
    AI->>AI: Run Market → Demand → Inventory → Strategy agents
    AI-->>SVC: Return RecommendationResult (price, confidence, rationale)
    SVC->>DB: Persist recommendation (status=pending)
    SVC-->>BP: Return recommendation object
    BP-->>F: 201 JSON Response
    F-->>U: Render recommendation card in UI
```

### Deployment Topology

```mermaid
graph LR
    subgraph CDN["🌐 Vercel CDN"]
        FE[React SPA\nStatically Built]
    end

    subgraph Render["☁️ Render Cloud"]
        BE[Flask API\nGunicorn WSGI]
        DB[(PostgreSQL\nManaged Instance)]
    end

    subgraph External["🔗 External"]
        AN[Anthropic API\nClaude Sonnet]
    end

    Browser -->|HTTPS| FE
    FE -->|REST API Calls| BE
    BE -->|SQL via SQLAlchemy| DB
    BE -->|LLM Calls| AN
```

---

## 🧠 Multi-Agent AI System

Klypup's intelligence layer is not a monolithic model call. It is a **structured multi-agent orchestration system** where each agent has a defined scope, input contract, and output contract — enabling modular reasoning and traceable decision-making.

### Agent Architecture

```mermaid
graph TD
    CTX[Product Context\nInventory + History + Config]
    CTX --> MA
    CTX --> DA
    CTX --> IA

    subgraph Agents["Specialist Agents"]
        MA["🌐 Market Intelligence Agent\nCompetitor analysis\nMarket positioning\nExternal demand signals"]
        DA["📉 Demand Forecast Agent\nSales velocity trends\nSeasonal modeling\nElasticity signals"]
        IA["📦 Inventory Agent\nStock level analysis\nDays-of-supply calc\nReorder flag detection"]
    end

    MA -->|market_signal| PA
    DA -->|demand_signal| PA
    IA -->|inventory_signal| PA

    subgraph Strategy["Strategy Layer"]
        PA["🎯 Pricing Strategy Agent\nSignal synthesis\nRecommended price calc\nConfidence scoring\nRationale generation"]
    end

    PA --> OUT[RecommendationResult\nprice | confidence | rationale | signals]
```

### Agent Responsibilities

#### 🌐 Market Intelligence Agent
**Scope:** External competitive context  
**Inputs:** Product category, current price, market segment  
**Outputs:** `market_signal` — competitive positioning score, suggested price band, market pressure indicator  
**LLM Role:** Synthesizes structured competitive context into pricing pressure signal with qualitative market assessment

#### 📉 Demand Forecast Agent
**Scope:** Historical demand modeling and forward projection  
**Inputs:** Sales history, product metadata, time-series features  
**Outputs:** `demand_signal` — demand trend direction, velocity score, elasticity estimate  
**LLM Role:** Interprets demand patterns and generates forward-looking demand pressure with confidence weighting

#### 📦 Inventory Agent
**Scope:** Current stock state and inventory health  
**Inputs:** Current stock level, reorder threshold, sales velocity  
**Outputs:** `inventory_signal` — stock health score, recommended pricing adjustment direction (clearance vs. premium)  
**LLM Role:** Maps inventory state to pricing strategy (overstocked → discount pressure; understocked → premium opportunity)

#### 🎯 Pricing Strategy Agent (Orchestrator Apex)
**Scope:** Cross-signal synthesis and final recommendation  
**Inputs:** `market_signal` + `demand_signal` + `inventory_signal` + product config + pricing constraints  
**Outputs:** `recommended_price`, `confidence_score`, `rationale`, `agent_contributions`  
**LLM Role:** Final synthesis agent that weighs all upstream signals and generates a structured, explainable recommendation with full reasoning chain

### Confidence Scoring

```
confidence_score = weighted_average(
    market_signal.confidence   × 0.30,
    demand_signal.confidence   × 0.35,
    inventory_signal.confidence × 0.20,
    strategy_alignment_score   × 0.15
)
```

Confidence scores below `0.65` are surfaced with a visual warning in the approval UI, prompting heightened review scrutiny.

### Explainability Output Structure

```json
{
  "recommended_price": 149.99,
  "confidence_score": 0.82,
  "rationale": "Strong demand trend combined with tightening inventory supports a 12% price increase. Competitive analysis confirms pricing headroom below market ceiling.",
  "agent_contributions": {
    "market_intelligence": {
      "signal": "below_market",
      "price_band": [145.00, 165.00],
      "confidence": 0.85
    },
    "demand_forecast": {
      "trend": "increasing",
      "velocity_score": 0.78,
      "confidence": 0.80
    },
    "inventory_analysis": {
      "stock_health": "tightening",
      "days_of_supply": 14,
      "confidence": 0.88
    }
  }
}
```

---

## 👤 Human-in-the-Loop Workflow

Klypup is architecturally designed around the principle that **AI recommendations must earn human trust before modifying operational data**. The approval workflow is not a UI feature — it is a core system constraint.

### Workflow State Machine

```mermaid
stateDiagram-v2
    [*] --> Pending: AI Recommendation Generated
    Pending --> UnderReview: Manager Opens Review
    UnderReview --> Approved: Manager Approves
    UnderReview --> Rejected: Manager Rejects
    Approved --> PriceUpdated: Product Price Modified
    PriceUpdated --> Logged: Audit Record Created
    Rejected --> Logged: Audit Record Created
    Logged --> [*]
```

### Workflow Detail

| Stage | Actor | System Action | Data State |
|---|---|---|---|
| **1. Generation** | AI Orchestrator | Creates recommendation record | `status = pending` |
| **2. Queue** | Manager (viewer) | Sees recommendation in pending queue | Read-only display |
| **3. Review** | Manager | Opens explainability panel | Full rationale visible |
| **4. Decision** | Manager | Approves or rejects with optional comment | Decision recorded |
| **5. Price Update** | System (automated) | If approved: updates `product.current_price` | Atomic transaction |
| **6. Audit Log** | System (automated) | Creates immutable audit record | Permanent record |

### Governance Principles

- **Zero auto-execution:** No recommendation modifies product prices without explicit human approval
- **Full explainability at decision point:** Managers see complete agent rationale before acting
- **Role enforcement:** Only users with `manager` or `admin` role can approve/reject
- **Audit completeness:** Approval, rejection, timestamp, reviewer identity, and resulting price are all logged
- **Rejection feedback loop:** Rejection reasons are stored and can inform future agent calibration

---

## 🖥️ Frontend Architecture

### Application Structure

```
src/
├── components/
│   ├── layout/
│   │   ├── Navbar.jsx              # Auth-aware navigation with role display
│   │   └── ProtectedRoute.jsx      # JWT-gated route wrapper
│   ├── dashboard/
│   │   ├── DashboardHome.jsx       # Portfolio overview + KPI cards
│   │   ├── ProductCard.jsx         # Product tile with status indicators
│   │   └── MetricsSummary.jsx      # Aggregated metrics panel
│   ├── recommendations/
│   │   ├── RecommendationsList.jsx # Paginated recommendation feed
│   │   ├── RecommendationCard.jsx  # Individual rec with explainability panel
│   │   └── AgentBreakdown.jsx      # Visual agent contribution display
│   ├── approvals/
│   │   ├── PendingQueue.jsx        # Approval workflow management view
│   │   └── ApprovalAction.jsx      # Approve/reject action component
│   └── audit/
│       └── AuditLog.jsx            # Historical decision log with filters
├── pages/
│   ├── Login.jsx                   # JWT auth entry point
│   ├── Dashboard.jsx               # Main operational view
│   ├── Products.jsx                # Product portfolio management
│   ├── Recommendations.jsx         # AI recommendation browser
│   ├── Approvals.jsx               # Workflow management (manager+)
│   └── Audit.jsx                   # Audit history (manager+)
├── services/
│   └── api.js                      # Axios instance with JWT interceptor
├── context/
│   └── AuthContext.jsx             # Global auth state + token management
└── App.jsx                         # Router + protected route configuration
```

### Routing Architecture

```mermaid
graph TD
    Root["/"] --> Login["/login\n Public Route"]
    Root --> Dashboard["/dashboard\n Protected"]
    Root --> Products["/products\n Protected"]
    Root --> Recommendations["/recommendations\n Protected"]
    Root --> Approvals["/approvals\n Manager+ Only"]
    Root --> Audit["/audit\n Manager+ Only"]

    Dashboard --> PRD[ProtectedRoute\nJWT Check]
    Approvals --> RBAC[RBACGuard\nRole Validation]
```

### State Management

Klypup uses **React Context + local component state** — a deliberate architectural choice that avoids the overhead of Redux for an application with well-defined, role-scoped data boundaries. The `AuthContext` manages:
- JWT token storage and retrieval
- Decoded user identity (role, org_id, email)
- Login/logout lifecycle

Per-page data is fetched on mount via `useEffect` + `axios`, keeping state colocated with the component that owns it. This architecture scales cleanly to the application's scope while remaining understandable without external state management tooling.

### API Integration

```javascript
// services/api.js — Axios instance with automatic JWT injection
const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
```

All API calls are centralized through this instance, ensuring JWT is always attached and that base URL configuration is environment-driven.

---

## ⚙️ Backend Architecture

### Blueprint Structure

```
backend/
├── app/
│   ├── __init__.py                 # App factory + blueprint registration
│   ├── models/
│   │   ├── user.py                 # User + organization model
│   │   ├── product.py              # Product model with org isolation
│   │   ├── recommendation.py       # Recommendation schema
│   │   └── audit.py                # Audit log model
│   ├── routes/
│   │   ├── auth.py                 # /api/auth/ — login, register
│   │   ├── products.py             # /api/products/ — CRUD + org-scoped
│   │   ├── recommendations.py      # /api/recommendations/ — generate + list
│   │   ├── approvals.py            # /api/approvals/ — workflow actions
│   │   └── audit.py                # /api/audit/ — immutable log access
│   ├── services/
│   │   ├── recommendation_service.py   # Orchestration coordinator
│   │   └── audit_service.py            # Audit record creation
│   ├── ai/
│   │   ├── orchestrator.py             # PricingOrchestrator — agent runner
│   │   ├── agents/
│   │   │   ├── market_agent.py         # Market Intelligence Agent
│   │   │   ├── demand_agent.py         # Demand Forecast Agent
│   │   │   ├── inventory_agent.py      # Inventory Analysis Agent
│   │   │   └── pricing_agent.py        # Pricing Strategy Agent
│   │   └── schemas.py                  # Pydantic contracts for agent I/O
│   └── middleware/
│       ├── auth_middleware.py          # JWT validation decorator
│       └── rbac.py                     # Role enforcement decorator
├── migrations/                         # Flask-Migrate / Alembic migrations
├── config.py                           # Environment config classes
└── run.py                              # Application entry point
```

### Service Layer Architecture

The backend enforces a clean **three-tier separation**:

1. **Route Layer** — HTTP handling only: parse request, validate input, call service, return response
2. **Service Layer** — Business logic: coordinate between AI orchestrator and database operations
3. **AI Layer** — AI orchestration only: no direct DB access, pure reasoning from context passed by service

This separation ensures AI logic is independently testable and swappable without touching HTTP or persistence layers.

### RBAC Middleware

```python
def require_role(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            claims = get_jwt_identity()
            if claims['role'] not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

# Usage
@approvals_bp.route('/<int:rec_id>/approve', methods=['POST'])
@jwt_required()
@require_role('manager', 'admin')
def approve_recommendation(rec_id):
    ...
```

### Organization Isolation Pattern

Every database query in the application includes an `org_id` filter derived from the authenticated JWT claims — enforced at the service layer, not the route layer:

```python
def get_products(org_id: int) -> list[Product]:
    return Product.query.filter_by(org_id=org_id, is_active=True).all()
```

No route handler ever passes `org_id` from the request body — it is always extracted from the validated JWT token, making tenant spoofing structurally impossible.

---

## 🗄️ Database Design

### Entity Relationship Diagram

```mermaid
erDiagram
    ORGANIZATION {
        int id PK
        string name
        string slug
        timestamp created_at
    }

    USER {
        int id PK
        int org_id FK
        string email
        string password_hash
        string role
        timestamp created_at
    }

    PRODUCT {
        int id PK
        int org_id FK
        string name
        string sku
        string category
        decimal current_price
        decimal cost_price
        int stock_quantity
        int reorder_threshold
        boolean is_active
        timestamp updated_at
    }

    RECOMMENDATION {
        int id PK
        int org_id FK
        int product_id FK
        int generated_by FK
        decimal recommended_price
        decimal original_price
        float confidence_score
        string status
        json agent_signals
        text rationale
        timestamp generated_at
    }

    APPROVAL {
        int id PK
        int recommendation_id FK
        int reviewed_by FK
        string decision
        text comment
        timestamp reviewed_at
    }

    AUDIT_LOG {
        int id PK
        int org_id FK
        int user_id FK
        int product_id FK
        int recommendation_id FK
        string action_type
        decimal price_before
        decimal price_after
        json metadata
        timestamp created_at
    }

    ORGANIZATION ||--o{ USER : "has"
    ORGANIZATION ||--o{ PRODUCT : "owns"
    ORGANIZATION ||--o{ RECOMMENDATION : "scopes"
    ORGANIZATION ||--o{ AUDIT_LOG : "scopes"
    USER ||--o{ RECOMMENDATION : "generates"
    PRODUCT ||--o{ RECOMMENDATION : "receives"
    RECOMMENDATION ||--o| APPROVAL : "reviewed_by"
    USER ||--o{ APPROVAL : "performs"
    RECOMMENDATION ||--o{ AUDIT_LOG : "produces"
```

### Why PostgreSQL?

**PostgreSQL was chosen deliberately** over NoSQL alternatives for the following reasons:

- **Relational integrity matters here.** Recommendations, approvals, products, and audit records have hard foreign key relationships that must be enforced — not suggested.
- **Audit trails require transactionality.** Approval + price update + audit log must execute atomically. PostgreSQL's ACID guarantees make this reliable without custom rollback logic.
- **Multi-tenancy is simpler with SQL.** Row-level `org_id` filtering is a standard, well-understood SQL pattern. It's performant, indexable, and auditable.
- **JSON columns for structured flexibility.** `agent_signals` and `metadata` columns use PostgreSQL's `JSONB` type, giving the AI layer schema flexibility without sacrificing relational structure for the rest of the model.

---

## 🛠️ Tech Stack

### Frontend
| Technology | Version | Role |
|---|---|---|
| React | 18 | Component framework |
| React Router | v6 | Client-side routing + protected routes |
| Axios | Latest | HTTP client with JWT interceptor |
| Vite | 5.x | Build tooling and dev server |
| CSS Modules / Tailwind | — | Component styling |

### Backend
| Technology | Version | Role |
|---|---|---|
| Python | 3.11 | Runtime |
| Flask | 3.x | WSGI web framework |
| Flask-JWT-Extended | Latest | JWT auth + claims management |
| Flask-SQLAlchemy | Latest | ORM |
| Flask-Migrate | Latest | Schema migrations (Alembic) |
| Flask-CORS | Latest | Cross-origin request handling |
| Gunicorn | Latest | Production WSGI server |

### AI & Intelligence
| Technology | Role |
|---|---|
| Anthropic Claude (claude-sonnet) | LLM backbone for all 4 agents |
| Anthropic Python SDK | Agent API calls |
| Custom Orchestrator | Sequential multi-agent coordination |
| Pydantic | Agent I/O schema validation |

### Database
| Technology | Role |
|---|---|
| PostgreSQL 15 | Primary relational database |
| SQLAlchemy ORM | Database abstraction layer |
| Alembic | Schema migration management |

### Deployment & Infrastructure
| Service | Purpose |
|---|---|
| Vercel | Frontend static hosting + CDN |
| Render | Backend hosting + managed PostgreSQL |
| GitHub Actions | CI/CD pipeline (optional) |
| dotenv | Environment variable management |

---

## 🎬 Live Demo & Screenshots

<div align="center">

### 🚀 Try It Live

[![Open App](https://img.shields.io/badge/🚀%20Open%20App-Live%20Demo-22c55e?style=for-the-badge)](https://your-frontend-url.vercel.app)
[![API Explorer](https://img.shields.io/badge/📡%20API-Live%20Endpoint-3b82f6?style=for-the-badge)](https://your-backend-url.onrender.com/api/health)

**Demo Credentials:**
```
Email:    demo@klypup.com
Password: demo1234
Role:     manager
```

</div>

---

### 📸 Application Screenshots

#### Dashboard — Portfolio Overview
> *Main operational view showing product portfolio, recommendation queue status, and KPI summary cards*

```
[ Screenshot: dashboard-overview.png ]
```

#### AI Recommendation Generation
> *Triggering multi-agent orchestration for a product and viewing the structured result*

```
[ Screenshot: recommendation-generation.png ]
```

#### Explainability Panel — Agent Breakdown
> *Per-agent signal visualization with confidence scores and rationale text*

```
[ Screenshot: explainability-panel.png ]
```

#### Approval Workflow — Pending Queue
> *Manager view of pending recommendations with explainability and action controls*

```
[ Screenshot: approval-queue.png ]
```

#### Audit Log — Decision History
> *Immutable audit trail with filterable decision history*

```
[ Screenshot: audit-log.png ]
```

---

### 🎥 Demo Walkthrough

**Recommended demo sequence for maximum impact:**

1. **Login** → Show JWT auth flow and role-based navigation
2. **Dashboard** → Show portfolio overview and KPI cards
3. **Products** → Browse product catalog with inventory indicators
4. **Generate Recommendation** → Trigger multi-agent AI orchestration in real-time
5. **Explainability Panel** → Open agent breakdown: market, demand, inventory signals
6. **Approval Queue** → Review pending recommendation as manager
7. **Approve** → Watch price update propagate to product card in real-time
8. **Audit Log** → Show immutable record of the completed workflow

---

## 🚀 Installation & Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15
- Anthropic API key

### Backend Setup

```bash
# Clone repository
git clone https://github.com/yourusername/klypup.git
cd klypup/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your values (see Environment Variables below)

# Run database migrations
flask db upgrade

# Seed initial data (optional)
python seed.py

# Start development server
flask run --port 5000
```

### Frontend Setup

```bash
cd ../frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Set VITE_API_URL=http://localhost:5000

# Start development server
npm run dev
```

### Environment Variables

#### Backend `.env`
```env
# Flask
SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/klypup

# JWT
JWT_SECRET_KEY=your-jwt-secret-here
JWT_ACCESS_TOKEN_EXPIRES=86400

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# CORS
FRONTEND_URL=http://localhost:5173
```

#### Frontend `.env.local`
```env
VITE_API_URL=http://localhost:5000
```

### Production Deployment

#### Backend (Render)
```
Build Command:   pip install -r requirements.txt
Start Command:   gunicorn run:app --workers 2 --bind 0.0.0.0:$PORT
Environment:     Set all backend env vars in Render dashboard
Database:        Attach Render managed PostgreSQL instance
```

#### Frontend (Vercel)
```
Framework:      Vite
Build Command:  npm run build
Output Dir:     dist
Environment:    VITE_API_URL=https://your-backend.onrender.com
```

---

## 📡 API Documentation

### Authentication

All protected endpoints require:
```
Authorization: Bearer <jwt_token>
```

### Endpoints

#### Auth

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/register` | None | Register organization + admin user |
| `POST` | `/api/auth/login` | None | Authenticate, receive JWT |
| `GET` | `/api/auth/me` | Required | Get current user profile |

#### Products

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| `GET` | `/api/products/` | Required | Any | List org products |
| `POST` | `/api/products/` | Required | Admin | Create product |
| `GET` | `/api/products/:id` | Required | Any | Get product detail |
| `PUT` | `/api/products/:id` | Required | Admin | Update product |
| `DELETE` | `/api/products/:id` | Required | Admin | Soft-delete product |

#### Recommendations

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| `POST` | `/api/recommendations/` | Required | Manager+ | Generate AI recommendation |
| `GET` | `/api/recommendations/` | Required | Any | List recommendations |
| `GET` | `/api/recommendations/:id` | Required | Any | Get recommendation + agent detail |

#### Approvals

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| `GET` | `/api/approvals/pending` | Required | Manager+ | List pending recommendations |
| `POST` | `/api/approvals/:id/approve` | Required | Manager+ | Approve recommendation |
| `POST` | `/api/approvals/:id/reject` | Required | Manager+ | Reject recommendation |

#### Audit

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| `GET` | `/api/audit/` | Required | Manager+ | List audit log (org-scoped) |
| `GET` | `/api/audit/:id` | Required | Manager+ | Get single audit record |

### Example: Generate Recommendation

**Request**
```http
POST /api/recommendations/
Authorization: Bearer eyJhbGc...
Content-Type: application/json

{
  "product_id": 42
}
```

**Response `201 Created`**
```json
{
  "id": 107,
  "product_id": 42,
  "recommended_price": 149.99,
  "original_price": 134.99,
  "confidence_score": 0.82,
  "status": "pending",
  "rationale": "Strong demand trend and tightening inventory support a 11.1% price increase. Market analysis confirms headroom below competitive ceiling.",
  "agent_signals": {
    "market_intelligence": { "signal": "below_market", "confidence": 0.85 },
    "demand_forecast": { "trend": "increasing", "velocity_score": 0.78, "confidence": 0.80 },
    "inventory_analysis": { "health": "tightening", "days_of_supply": 14, "confidence": 0.88 }
  },
  "generated_at": "2025-08-14T10:32:07Z"
}
```

### Example: Approve Recommendation

**Request**
```http
POST /api/approvals/107/approve
Authorization: Bearer eyJhbGc...
Content-Type: application/json

{
  "comment": "Aligns with Q3 margin targets. Approved."
}
```

**Response `200 OK`**
```json
{
  "recommendation_id": 107,
  "decision": "approved",
  "product_updated": true,
  "new_price": 149.99,
  "audit_log_id": 291,
  "reviewed_at": "2025-08-14T10:35:22Z"
}
```

---

## 🔐 Security & Multi-Tenancy

### JWT Authentication

- Tokens are signed with `HS256` using a server-side secret never exposed to clients
- Token payload includes: `user_id`, `org_id`, `role`, `exp`
- Token expiry: 24 hours (configurable per environment)
- No refresh token implementation (intentional for operational simplicity in v1; roadmapped for v2)

### Role-Based Access Control

| Role | Products | Generate Recs | Approve/Reject | View Audit | Manage Users |
|---|---|---|---|---|---|
| `viewer` | Read | ✗ | ✗ | ✗ | ✗ |
| `manager` | Read | ✓ | ✓ | ✓ | ✗ |
| `admin` | Full CRUD | ✓ | ✓ | ✓ | ✓ |

RBAC is enforced via **Python decorators on route handlers** — not in frontend logic. Frontend role-gating is UX-only; API enforcement is the authoritative layer.

### Multi-Tenant Data Isolation

```python
# Every service method enforces org_id from JWT — not from request
def get_recommendations(org_id: int):
    return Recommendation.query.filter_by(org_id=org_id).all()
```

- `org_id` is **never** accepted from request bodies or query params
- All data access is filtered through the authenticated org_id extracted from the JWT
- Cross-tenant data access is structurally impossible without a valid token from that organization

### API Security Posture

- CORS restricted to configured `FRONTEND_URL` origin
- All inputs validated before service layer execution
- SQL injection protected via SQLAlchemy ORM parameterization
- No raw SQL queries in application code
- Error responses never expose internal stack traces in production mode

---

## 📈 Scalability & Roadmap

### Near-Term Improvements

**Async AI Orchestration**  
Current agent calls are synchronous within a request. Moving to **Celery + Redis** would allow recommendation generation to happen asynchronously, with the frontend polling or subscribing to completion events — enabling better UX and horizontal scaling of the AI layer.

**Event-Driven Audit Architecture**  
Replace direct audit log writes with an **event queue** (e.g., SQS or Redis Streams) so that audit records are written by a dedicated consumer — decoupling audit reliability from request throughput.

**Real-Time Notifications**  
Add **WebSocket** or **SSE** channels for live notification when recommendations enter the pending queue — enabling managers to act without polling.

### Medium-Term Vision

**Agent Memory & Context Persistence**  
Implement vector database storage (e.g., **Pinecone** or **pgvector**) of historical recommendations and outcomes. Agents could retrieve similar historical decisions as few-shot context, improving recommendation quality over time through operational learning.

**Streaming Analytics Integration**  
Connect to real-time sales data streams (**Kafka**, **Kinesis**) to give the Demand Forecast Agent live velocity signals rather than batch historical data.

**Microservices Decomposition**  
As the platform scales, the AI orchestration layer can be extracted into a dedicated **FastAPI microservice** with its own scaling policy — allowing AI compute to scale independently from the API layer.

**Autonomous Execution Mode**  
For high-confidence, low-risk recommendations (e.g., confidence > 0.95 within defined price change bounds), enable an **auto-approval mode** with audit logging and time-bounded rollback windows — reducing operational burden for routine pricing adjustments.

### Observability Roadmap

- Structured logging with **OpenTelemetry** traces per recommendation lifecycle
- Agent-level latency and confidence score dashboards via **Grafana**
- Recommendation acceptance rate tracking for agent performance calibration
- **LangFuse** or **Helicone** integration for LLM call observability and cost tracking

---

## 🔧 Engineering Decisions & Tradeoffs

### Why Flask over FastAPI?

Flask was chosen for its **minimal surface area and Blueprint-based modularity**. For an applied AI project focused on showcasing AI orchestration and business workflows, Flask's simplicity keeps the web framework layer transparent — the architecture is about the AI system, not the HTTP framework. FastAPI would be the natural next step for production async performance.

### Why React + Vite over Next.js?

A **pure SPA architecture** was chosen deliberately: Klypup is an operational dashboard, not a content site. SEO is irrelevant; authentication gating is universal. React + Vite gives a faster development loop and simpler deployment model (static build to CDN) without SSR complexity that adds no value for this use case.

### Why SQL over NoSQL?

Pricing decisions, approvals, and audit records are **inherently relational**. Foreign key integrity, atomic multi-table transactions, and row-level tenant isolation are SQL native — implementing these in MongoDB would require application-layer guarantees that are harder to reason about and audit. PostgreSQL was the correct choice.

### Why Multi-Agent Separation?

A single monolithic LLM prompt could theoretically generate a pricing recommendation. But **agent separation gives us**:
- Independent confidence scoring per domain
- Debuggable reasoning chains (which agent drove the recommendation?)
- Modular replaceability (swap the demand agent for a time-series ML model without touching other agents)
- Cleaner explainability output (per-agent signal is more trustworthy than a single opaque rationale)

### Why Mandatory Approval Workflow?

An AI system that auto-applies pricing changes is an AI system that **cannot be trusted in a production business context**. The approval workflow is the mechanism that makes Klypup production-viable: it turns an AI recommendation engine into a **decision support system** — a fundamentally different and more defensible product.

### Deployment Tradeoffs

- **Render cold starts:** The free tier backend may have cold start latency (~30–60s). Production tier eliminates this.
- **No background workers:** Current sync architecture blocks requests during AI orchestration. Acceptable for v1 demo load; requires Celery for production throughput.
- **Stateless API:** Horizontal scaling is straightforward — no server-side session state.

---

## 🏁 Conclusion

**Klypup** is not a demo that proves you can call an LLM API. It is a demonstration that **applied AI engineering requires systems thinking** — architecture, governance, explainability, data integrity, and user trust are not decorative features. They are the product.

This platform represents the full stack of modern AI product engineering:

- **AI orchestration architecture** that is modular, explainable, and extensible
- **Governance design** that makes AI safe for operational deployment
- **Multi-tenant data architecture** that is secure by construction
- **Full-stack integration** from React UI through Flask API to LLM-backed agents
- **Business orientation** — pricing intelligence is a real problem with real economic impact

Klypup is designed to be extended, debated, and improved — not just demonstrated. Every architectural decision documented here was made with production intent: not to impress evaluators, but to build a system that could actually operate in a real business environment.

---

<div align="center">

**Built with precision. Designed for operations. Powered by collaborative AI.**

<br/>

[![Frontend](https://img.shields.io/badge/🚀%20Launch%20App-Live%20Demo-22c55e?style=for-the-badge)](https://your-frontend-url.vercel.app)
[![GitHub](https://img.shields.io/badge/⭐%20Star%20on-GitHub-0f172a?style=for-the-badge&logo=github)](https://github.com/yourusername/klypup)

<br/>

*Klypup — Dynamic Pricing Intelligence, Powered by Multi-Agent AI*

</div>

---

## 📋 Post-Generation Recommendations

### Suggested Improvements

**Architecture Enhancements**
- Add a health check endpoint (`/api/health`) that returns DB connectivity status — makes deployment debugging faster and looks professional in demos
- Implement request ID propagation (UUID per request in headers) for tracing across logs
- Add `pytest` test coverage for the service layer and agent orchestrator — even 5–10 targeted tests signal engineering maturity

**AI System Enhancements**
- Store raw LLM prompt/response pairs in a `llm_call_log` table — enables agent debugging, auditing, and future fine-tuning
- Add a `recommendation_feedback` table to capture post-hoc outcome tracking (did the price change achieve the expected result?)

---

### Screenshots to Capture

| Screenshot | What to Show | Why It Matters |
|---|---|---|
| Dashboard overview | Full portfolio with status badges | Shows product-grade UI quality |
| Recommendation generation | Loading state → result reveal | Shows real-time AI in action |
| Explainability panel expanded | All 3 agent cards with scores | The most technically impressive UI element |
| Approval queue (manager view) | Pending cards with action buttons | Shows governance design |
| Post-approval product card | Updated price with "approved" badge | Shows end-to-end workflow completion |
| Audit log | Timeline of decisions | Shows enterprise-grade audit design |
| Mobile responsive view | Dashboard on narrow viewport | Shows frontend engineering quality |

---

### Optimal Demo Order

1. **90-second pitch demo:** Login → Dashboard → Generate Recommendation → Show Explainability → Approve → Show Audit Log
2. **Technical deep-dive demo:** Architecture diagram → API call trace → Agent breakdown → Database schema → Code walkthrough of orchestrator
3. **Business value demo:** Open with the pricing problem statement → Show the recommendation workflow → Emphasize the governance model → Close with audit trail

---

### README Visual Enhancements

- Add a **hero banner image** (architecture diagram rendered as a PNG, centered above badges)
- Add **animated GIF** of the recommendation generation flow (most impactful single asset)
- Add a **"How It Works" 3-step visual** (Generate → Review → Update) as a simple SVG or image
- Use GitHub's built-in `[!NOTE]` and `[!IMPORTANT]` callout syntax for key architectural points
- Add a **contributors section** with your profile card if submitting solo

---

### Portfolio Presentation Tips

- **Lead with the governance angle:** Most AI projects skip the approval workflow. Emphasizing it differentiates Klypup as operationally-minded, not just technically impressive.
- **Diagram first, code second:** In any verbal walkthrough, show the multi-agent diagram before opening code. Architecture understanding signals seniority.
- **Quantify the business case:** "A 1% pricing improvement = 8–11% operating profit improvement" is a real number. Use it. It reframes the project from a coding exercise to a business solution.
- **Acknowledge tradeoffs explicitly:** In interviews, proactively naming what you'd improve (async orchestration, agent memory) signals architectural maturity.
- **Frame it as a platform, not a feature:** Klypup is not a pricing calculator. It's a pricing intelligence platform. Word choice matters in product conversations.
