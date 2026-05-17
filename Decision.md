
# DECISIONS.md
# Dynamic Pricing Intelligence Dashboard — Engineering Decisions
### Klypup Applied AI Intern Assessment — Option B

---

## 1. Why I Chose Option B

I chose the Dynamic Pricing Intelligence Dashboard because it sits at the intersection of the three areas I find most technically interesting: **multi-agent system design**, **human-in-the-loop workflow automation**, and **governance-first product thinking**.

Option A (Investment Research Dashboard) would have been a well-scoped retrieval-augmented generation system — query in, structured report out. Genuinely useful, but architecturally predictable. Option B demanded something more operationally complex: agents with distinct domains that *collaborate* to produce a recommendation, a *state machine* for approval workflows, an *audit trail* that captures the delta between what AI suggested and what humans actually executed, and a *configurable confidence threshold* that determines when the system earns the right to act autonomously.

That last point shaped my thinking throughout the build: the system should be designed to earn operational trust incrementally, not assume it. The confidence threshold mechanism and the human review queue are not just features — they are the core product hypothesis. An AI pricing engine that auto-executes everything is a liability. One that surfaces high-quality recommendations with full reasoning and routes uncertain decisions to human reviewers is something a real business would actually deploy.

Option B also had more interesting failure modes. Multi-agent coordination breaks in more instructive ways than a single RAG pipeline. Designing agent I/O contracts that are robust to LLM output variance — a genuinely hard problem — is more representative of production applied AI engineering than prompt templating.

---

## 2. Why This Tech Stack

### Frontend — React + Vite + React Router

**React** was the natural choice for this use case: a data-dense operational dashboard with multiple interactive panels (approval queue, explainability cards, audit log, product catalog) that update independently. React's component model handles this well. Framer Motion added polished transitions without meaningful complexity cost.

**Vite** over Create React App — faster hot module replacement during development, smaller build output, and zero configuration for Vercel deployment.

**Why not Next.js?** The application is entirely auth-gated. Every route requires a logged-in user. Server-side rendering provides no SEO benefit for an internal SaaS tool, and it would add deployment complexity (a Node.js server on Vercel instead of a pure static build) for zero user-facing benefit. Next.js is the correct choice when public-facing pages, SEO, or server-side data fetching at the page level are requirements — none of which apply here.

### Backend — Flask + SQLAlchemy

**Python** was required by the Anthropic SDK and Pydantic, which are central to the agent layer. Given a Python backend, the choice was Flask vs FastAPI.

**Flask** was chosen for its explicit, readable Blueprint architecture that maps cleanly to the domain's service boundaries. Each Blueprint corresponds to a distinct business domain: auth, products, recommendations, approvals, audit, config. Flask-JWT-Extended provided JWT with custom claims (org_id, role) out of the box with minimal configuration.

**Why not FastAPI?** FastAPI would be the correct upgrade for production — native async support matters for concurrent agent execution. In a 5-day build with synchronous orchestration, Flask's simplicity and my familiarity with its patterns made it the right call. The path to FastAPI is a drop-in replacement for route handlers; the service layer and orchestrator are framework-agnostic.

**Pydantic v2** was used for agent I/O contract validation. Every agent output is validated before being passed downstream. This is not optional in an LLM-powered pipeline — models occasionally return values outside expected literal sets, and catching that at the contract boundary is far preferable to propagating a broken signal into the Pricing Strategy Agent.

### Database — PostgreSQL

The decision between PostgreSQL and a document database (MongoDB, Firestore) was straightforward.

The approval workflow — update product price, update recommendation status, write audit log — must execute atomically. If the price update succeeds but the audit write fails, the database must roll back entirely. That is a hard ACID requirement. PostgreSQL's transaction semantics handle this reliably without custom recovery logic.

The `agent_signals` field is the one genuinely document-shaped piece of data: a nested object with per-agent outputs of varying structure. PostgreSQL's JSONB column type handles this without sacrificing relational integrity for the rest of the schema. JSONB also supports GIN indexing for future querying of agent signal patterns.

MongoDB would have required manual transaction orchestration (multi-document transactions exist but add complexity) and surrendered the referential integrity between products, recommendations, and audit logs that the schema relies on.

### Authentication — Flask-JWT-Extended

JWT was chosen over session-based auth for two reasons: the architecture requires the token to carry `org_id` and `role` as verified claims (not requiring a database lookup on every request), and JWT is stateless — appropriate for a REST API consumed by a single-page application.

The critical design decision: `org_id` is embedded in the JWT at login time by the server and never accepted from user-controlled input. This makes the tenant isolation guarantees as strong as the JWT signing secret.

### Deployment — Vercel + Render

**Vercel** for the frontend: zero-configuration static deployment, CDN edge distribution, automatic HTTPS, and instant rollbacks. Ideal for a Vite-built SPA.

**Render** for the backend and managed PostgreSQL: free tier supports persistent web services and managed database instances with private networking between them. The free tier cold-start behavior (30-second wake-up after inactivity) is a known limitation, documented in the README, and acceptable for a demo submission.

**Why not AWS?** AWS would be the correct production choice — ECS/Fargate for the backend, RDS for PostgreSQL, CloudFront for the frontend. The assessment notes AWS is a plus but not required. Given a 5-day timeline and the priority of shipping a complete, working product, Render + Vercel's zero-infrastructure-management model was the correct tradeoff. The application is architecturally ready for containerization and cloud migration.

---

## 3. Multi-Tenant Design Decisions

### Pattern Chosen: Shared Schema with `org_id` Column + Middleware Enforcement

I evaluated three multi-tenancy patterns:

| Pattern | Pros | Cons | Verdict |
|---|---|---|---|
| Separate database per tenant | Strongest isolation, easy backups | Ops overhead at scale, impractical for demo | Rejected |
| Separate schema per tenant | Strong isolation, shared infra | Complex migration management, requires dynamic schema routing | Rejected |
| Shared schema with `org_id` | Simple, proven, scales well | Requires disciplined query filtering | **Chosen** |

The shared schema approach is appropriate for this use case and correctly implements the isolation model that the assessment requires. Every tenant-scoped table (products, recommendations, audit_logs) carries an `org_id` foreign key column. Every service method receives `org_id` as a parameter extracted from the verified JWT — never from the request body or query string.

**Why middleware-level extraction matters.** If `org_id` were accepted from the client (e.g., in a request header or POST body), a malicious actor could set it to any value and access another tenant's data. By extracting it exclusively from the signed JWT payload, the isolation guarantee is as strong as the signing secret. The service layer never makes a trust decision — it receives a trusted `org_id` and filters by it.

**RBAC enforcement pattern.** Route-level Python decorators check the `role` claim from the verified JWT before the handler executes. Frontend role-gating (hiding admin navigation items from manager accounts) is a UX improvement only; the API is the authoritative enforcement boundary.

---

## 4. AI System Design Decisions

### Why Multi-Agent Architecture Over a Single Prompt

A single well-engineered prompt could produce a pricing recommendation. I rejected this approach for reasons that are architectural, not superficial.

**Traceable reasoning requires separated outputs.** The explainability panel — a core assessment requirement — is only possible because each agent produces a named, structured signal stored in the `agent_signals` JSONB column. A single prompt's reasoning is opaque; per-agent signals are explicitly attributable.

**Independent confidence scoring is meaningful.** When the Market Intelligence Agent reports 0.85 confidence and the Demand Forecasting Agent reports 0.58, the composite score reflects genuine uncertainty in the demand domain — not a single model's self-reported certainty about everything. Analysts can see which agent drove low confidence and adjust their review accordingly.

**Modular replaceability.** The Demand Forecasting Agent is currently LLM-based using mock trend data. The contract — a `DemandSignal` Pydantic model — is the seam. Replacing the agent implementation with a real ML time-series model requires no changes to the orchestrator or any other agent.

### Confidence Scoring Design

The weighted composite formula assigns higher weight to demand signals (0.35) than inventory signals (0.20) because demand elasticity is the primary driver of optimal pricing in e-commerce, while inventory constraints are secondary (they define the floor, not the optimal price). These weights are configurable in the architecture and should be tuned against historical decision outcomes in production.

The confidence threshold that separates auto-execution from human review is configurable per organization by admins. This is intentional: a new organization should start with a low threshold (routing most recommendations to human review) and raise it as they calibrate trust in the system's recommendations.

### Explainability as a First-Class Feature

The explainability panel was not an afterthought. It was a design constraint that shaped the agent architecture. Each recommendation must show: which agent contributed what signal, which data source fed that signal, the per-agent confidence, and the composite score with weights. This information is captured in the `agent_signals` JSONB column at generation time and rendered as structured UI cards.

The `ai_recommended_price` vs `applied_price` distinction in audit logs enables a future feedback loop: if analysts consistently override AI recommendations in a particular category by a consistent delta, that pattern is signal for threshold recalibration or agent prompt revision.

### Human-in-the-Loop as an Architectural Guarantee, Not a UX Feature

The approval workflow is enforced at the database level. A recommendation with `status="pending"` cannot cause a product price update. The price update, status transition, and audit log write are a single atomic transaction triggered only by an explicit approval action from a verified manager-role user. There is no code path in the application that updates a product price outside this transaction.

---

## 5. Tradeoffs Made Within 5 Days

### Synchronous Agent Orchestration

The most significant architectural tradeoff. The `PricingOrchestrator` runs agents sequentially in the HTTP request thread. The request blocks for 3–6 seconds during orchestration.

**What I chose instead:** A synchronous implementation that works, is demoable, and demonstrates the full agent architecture correctly. The loading state on the frontend handles the wait gracefully.

**What production requires:** Celery + Redis for async task execution, with the API returning a `task_id` immediately and the frontend polling or subscribing via SSE for completion. This is the first production upgrade.

### Mock Data Sources Only

No real competitor price APIs, Google Trends integration, or live e-commerce platform connections. The mock data generation scripts produce realistic patterns (seasonal variance, competitor price movements, inventory fluctuations) that give the AI agents meaningful signal to reason over.

**Why this was the right call:** The assessment explicitly permits synthetic data and requires data generation scripts. Integrating real external APIs would have consumed 2–3 days of the timeline on rate limit handling, API key management, and data normalization — time better spent on the multi-agent architecture, approval workflow, and multi-tenant implementation.

### No JWT Refresh Tokens

Access tokens expire after 24 hours with no silent refresh. Users must re-login after expiry.

**Production fix:** Refresh token rotation with sliding window expiry. Straightforward to implement; deprioritized in favor of core feature completeness.

### No Test Coverage

No pytest suite for the service layer or agent contracts; no Vitest coverage for frontend components.

**What I'd add first:** Tests for the `PricingOrchestrator` contract validation (does a malformed LLM response produce a correct fallback signal?), the approval transaction (does a database failure mid-transaction roll back correctly?), and the tenant isolation middleware (does an Org A token produce a 403 on Org B resources?).

---

## 6. Hardest Challenges

### Designing Agent I/O Contracts Robust to LLM Output Variance

The hardest technical problem was not writing agent prompts — it was designing the validation layer between agents so that LLM output variance doesn't break the pipeline.

Claude Sonnet is highly reliable, but "highly reliable" is not "always exactly conformant." Early in development, the Pricing Strategy Agent occasionally received a `DemandSignal` where `trend` was `"slight_increase"` instead of `"increasing"` — a literal value outside the Pydantic model's `Literal["increasing", "stable", "decreasing"]` constraint.

The solution was two-layered: tighter prompt engineering (explicitly listing valid literal values in the system prompt) and fallback handling in each agent that catches Pydantic validation errors and returns a low-confidence default signal rather than propagating the error. The orchestrator receives a valid, typed signal regardless — it just knows the agent had low confidence.

### Multi-Tenant Routing with RBAC Across All Endpoints

Ensuring that every API endpoint correctly enforces both authentication, tenant scoping, and role requirements simultaneously — without repeating the logic in every handler — required careful middleware design.

The solution: `@jwt_required()` handles authentication; a separate `@admin_required` decorator handles role checking; `org_id` extraction into a helper function called at the top of every service method handles tenant scoping. The three concerns are separated, composable, and individually testable.

### Frontend-Backend State Synchronization on Approval Actions

When a manager approves a recommendation, it should disappear from the pending queue immediately. The naive implementation — refetch the pending queue after approval — produces a flash of the approved item still appearing during the refetch. The solution was optimistic UI: remove the item from local React state immediately on action, then confirm with the server response. If the server returns an error, re-add the item and show an error message.

---

## 7. What I Would Improve With 2 More Weeks

### Week 1 — Architecture and Reliability

**Async agent execution (Celery + Redis).** Move the `PricingOrchestrator` to a Celery task queue. The API returns immediately with a `task_id`; the frontend subscribes via SSE for real-time agent progress updates ("Market Intelligence Agent complete — 85% confidence signal received"). This is the single highest-impact architectural change.

**JWT refresh tokens.** Add refresh token rotation with sliding window expiry and a React interceptor for silent token refresh.

**pytest coverage.** Unit tests for the orchestrator contract validation, approval transaction atomicity, and tenant isolation middleware. Integration tests for the recommendation generation and approval endpoints.

**Docker Compose.** One-command local setup: `docker-compose up` starts PostgreSQL, Flask, and the React dev server.

### Week 2 — Intelligence and Features

**Real competitor price scraping.** Replace mock data with a lightweight scraping service using a structured output parser. Even 3–5 real competitor price feeds would meaningfully improve recommendation quality demonstrations.

**SSE streaming for agent progress.** Real-time per-agent progress updates in the UI while orchestration runs. Requires the async execution work from Week 1.

**Admin analytics dashboard.** Metrics on override rate (how often analysts modify vs accept AI recommendations), confidence score distribution over time, and per-category recommendation accuracy. This is the feedback loop that enables threshold calibration.

**Vector search for similar historical decisions.** Store recommendation embeddings in pgvector. The Pricing Strategy Agent retrieves semantically similar past decisions as few-shot context, improving consistency over time.

**CI/CD pipeline.** GitHub Actions: lint (flake8, ESLint), test (pytest, Vitest), build verification on every pull request; automatic deployment to Render/Vercel on merge to main.

**Real-time competitor monitoring.** A background job that polls competitor prices on a schedule and flags products where the market position has shifted since the last recommendation — surfacing them at the top of the product catalog with a "re-price needed" badge.

---

## 8. Product Thinking Reflection

### AI as a Feature That Earns Its Place

The assessment's framing — "AI is a feature inside the product, not the product itself" — shaped every design decision. The multi-agent engine is powerful, but the product's value is the *operational workflow* it enables: a pricing analyst who previously spent most of her time gathering data can now spend that time reviewing AI-generated recommendations with full reasoning, approving the ones she trusts, and overriding the ones where her domain expertise says the AI is wrong.

The explainability panel exists because approvals without understanding are not governance — they are rubber-stamping. A manager who clicks "approve" without understanding why the system recommended a 10% price drop is not exercising human oversight; she is just adding latency to an automated process. The explainability panel makes the reasoning visible enough that approval is a genuine decision.

### The Confidence Threshold as a Trust Calibration Mechanism

The configurable confidence threshold is not a parameter — it is a product philosophy. New organizations should start with a low threshold, requiring human review for almost everything. As they observe the system's recommendations, understand where it is reliable and where it is uncertain, and build calibrated trust, they raise the threshold. The organization earns the system's autonomy incrementally.

This also creates a natural feedback loop: the `ai_recommended_price` vs `applied_price` delta in audit logs, aggregated over time, tells you exactly where human judgment consistently diverges from AI judgment. That is the signal for retraining, threshold adjustment, or identifying categories where the current agent inputs are insufficient.

### Governance as a Competitive Advantage

Enterprise SaaS buyers increasingly require that AI-powered tools be auditable, explainable, and governed. The audit trail, approval workflow, and explainability panel are not compliance features — they are the product's argument that AI can be trusted in an operational pricing context. A competitor product that auto-executes everything will close fewer enterprise deals than one that can demonstrate a complete decision history with reviewer identity, timestamps, and the explicit record of human oversight.

Building governance into the architecture from day one — rather than bolting it on after — is the difference between an AI demo and a system a real business would deploy.

---

*Document version 1.0 — Klypup Applied AI Intern Assessment — Option B submission*
