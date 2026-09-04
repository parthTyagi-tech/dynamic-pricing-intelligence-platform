# Fully Agentic Multi-Platform Live Price Recommendation System (v2)
## Technical Architecture & Security Specification

---

## 1. System Overview & Agentic Philosophy

The **Fully Agentic Multi-Platform Live Price Recommendation System** is designed for offline-catalog e-commerce merchants who need autonomous, intelligent, and tamper-resistant price optimization without a continuous ERP integration. Rather than executing a brittle, hardcoded pipeline or static scraping script, the system orchestrates a swarm of **goal-directed autonomous agents**.

Each agent operates on a continuous **Plan $\rightarrow$ Act $\rightarrow$ Observe $\rightarrow$ Evaluate $\rightarrow$ Adapt** loop:
- Agents maintain internal working memory across iterations.
- If a scraper encounters anti-bot detection (Cloudflare, CAPTCHA), it does not merely fail: it shifts strategies (e.g., switches headers/proxies, drops strict filters, relaxes title search tokens, or falls back to headless rendering).
- If multiple platforms fail or trip circuit breakers, the downstream Pricing Reasoning Agent observes the degraded signal, dynamically adjusts its confidence score, factors in the uncertainty, and flags human oversight if necessary.
- Code-level financial guardrails (margin floors, price sanity limits) prevent catastrophic algorithmic repricing regardless of LLM hallucinations.

```
                    ┌─────────────────────────┐
                    │   Catalog CSV Upload    │
                    └────────────┬────────────┘
                                 │
                                 ▼
                     ┌───────────────────────┐
                     │   Supervisor Agent    │◄─────────────────┐
                     │ (Idempotency & Route) │                  │
                     └───────────┬───────────┘                  │
                                 │ Dispatches                   │
                   ┌─────────────┴─────────────┐                │
                   ▼                           ▼                │
         ┌───────────────────┐       ┌───────────────────┐      │
         │ Platform Scraper  │  ...  │ Platform Scraper  │      │ Event Bus
         │   (Amazon / etc.) │       │  (Flipkart / etc) │      │ (Local / GCP PubSub)
         └─────────┬─────────┘       └─────────┬─────────┘      │
                   └─────────────┬─────────────┘                │
                                 ▼                              │
                     ┌───────────────────────┐                  │
                     │   Aggregator Agent    │──────────────────┤
                     │(Match Score & Outlier)│                  │
                     └───────────┬───────────┘                  │
                                 ▼                              │
                     ┌───────────────────────┐                  │
                     │Pricing Reasoning Agent│──────────────────┤
                     │(Floor Clamp & Sanity) │                  │
                     └───────────┬───────────┘                  │
                                 ▼                              │
                     ┌───────────────────────┐                  │
                     │    Approval Agent     │                  │
                     │  (Human-in-the-Loop)  │                  │
                     └───────────┬───────────┘                  │
                                 │ Approved                     │
                                 ▼                              │
                     ┌───────────────────────┐                  │
                     │ Catalog Update Agent  │──────────────────┘
                     │(Atomic Commit & Audit)│
                     └───────────────────────┘
```

---

## 2. Agent Roster & Autonomous Capabilities

### 2.1 Supervisor Agent (`backend/app/services/agentic/supervisor_agent.py`)
- **Primary Goal**: Plan scraper assignment, avoid duplicate runs via idempotency checks, isolate tenant domains, and coordinate the lifecycle of each pricing task.
- **Dynamic Routing**: Inspects product category and dispatches only to relevant platforms (e.g., electronics $\rightarrow$ Amazon, Flipkart, Croma, Reliance Digital; fashion $\rightarrow$ Myntra, Ajio, Nykaa).
- **Circuit Breaker Aware**: Queries `ScraperReliability` state before dispatch. If a platform's breaker is `OPEN`, skips immediately or assigns an alternate target, notifying the event bus with explicit attribution.
- **Idempotency Guard**: Hashes `(org_id, product_id, current_price, competitor_snapshot)` with a 20-minute sliding TTL. If an identical recommendation was generated within that window, returns cached results directly.

### 2.2 Category Platform Scrapers (`backend/app/services/agentic/scrapers/`)
- **Primary Goal**: Extract live competitor pricing, stock status, ratings, and canonical URLs while remaining undetected.
- **Anti-Detection & Adaptation**:
  1. *Tier 1: Fast HTTP/JSON*: Dynamic browser headers, user-agent pool rotation, TLS fingerprint randomization.
  2. *Tier 2: Headless Browser*: Playwright / Puppeteer with stealth plugins for dynamic Single-Page Applications (SPAs).
  3. *Tier 3: Query Relaxation*: Drops high-specificity tokens (e.g., color/packaging variants) while computing Levenshtein and token match scores to guarantee product identity.
- **Product-Match Confidence Scoring**: Evaluates candidate matches using brand, model number, category, and token overlap ($0.0 - 1.0$). Matches with score $< 0.65$ are marked `unverified_match` and quarantined from automatic pricing calculations.

### 2.3 Aggregator Agent (`backend/app/services/agentic/aggregator_agent.py`)
- **Primary Goal**: Synthesize multi-source intelligence into a sanitized market baseline.
- **Intelligence Processing**:
  - Excludes `unverified_match` candidates to prevent catalog contamination.
  - Computes min, max, median, and mean competitor prices.
  - Applies statistical interquartile range (IQR) outlier filtering to eliminate spoofed prices ($1$ INR promotions or extreme outliers).
  - Explicitly documents missing or failed platforms so downstream reasoning knows the data density.

### 2.4 Pricing Reasoning Agent (`backend/app/services/agentic/pricing_reasoning_agent.py`)
- **Primary Goal**: Derive an optimal price recommendation that balances competitiveness with gross margin viability.
- **Strict Code-Enforced Financial Guardrails**:
  - **Margin Floor Clamp**: Hard minimum calculated in code:
    $$\text{Price Floor} = \text{Cost Price} \times \left(1 + \frac{\text{Min Margin \%}}{100}\right)$$
    The recommendation engine *never* permits a price below this floor, regardless of LLM generation. If the raw target is below the floor, it clamps to the floor and sets `margin_floor_applied = True`.
  - **Sanity Bound Check**: Flags any price swing exceeding $\pm 50\%$ from the current catalog price as `sanity_bound_flagged = True`, mandating manual human sign-off.
  - **Confidence Weighting**: Degrades confidence proportionally if fewer than 2 platforms returned verified data.

### 2.5 Approval Agent (`backend/app/services/agentic/approval_agent.py`)
- **Primary Goal**: Secure human-in-the-loop review interface.
- **Enforcement**:
  - Auto-approves recommendations *only* if confidence $\ge 0.85$, sanity bound is unflagged, and organization auto-approve policy is active.
  - Enforces tenant isolation (SEC-1, SEC-2): Users can only approve or reject tasks belonging to their active `organization_id`.

### 2.6 Catalog Update Agent (`backend/app/services/agentic/catalog_update_agent.py`)
- **Primary Goal**: Safely commit accepted repricing decisions to the permanent database.
- **Atomic Operations**:
  - Runs in an isolated DB transaction (`db.session.begin_nested()` / `commit()`).
  - Writes new price to `Product.current_price`.
  - Appends an immutable record to `PriceHistory` (`old_price`, `new_price`, `competitor_snapshot`, `approved_by`).
  - Records an immutable `AuditLog` entry with `before_value` and `after_value`.

### 2.7 Notification Agent (`backend/app/services/agentic/notification_agent.py`)
- **Primary Goal**: Notify operations teams of completed recommendations, margin alerts, or circuit breaker trips.
- **Sanitization**: Employs auto-escaped Jinja2 templates and strict string sanitization (SEC-11) to prevent HTML/template injection.

---

## 3. Product Category to Platform Routing Matrix

| Category Code | Platform Targets | Scraper Strategy & Adapters |
|---|---|---|
| `electronics` | Amazon, Flipkart, Croma, Reliance Digital | Model number & specs token matching; Playwright for dynamic price grids. |
| `fashion` | Myntra, Ajio, Nykaa Fashion, Amazon | Size/color matrix extraction; query relaxation on seasonal sub-brands. |
| `beauty` | Nykaa, Purplle, Amazon, Flipkart | Shade/volume normalization; unverified filtering on bundles. |
| `groceries` | Blinkit, Zepto, Swiggy Instamart, BigBasket | Pincode/Geo-locality headers; unit price per gram/ml normalization. |
| `books` | Amazon, Flipkart, Bookswagon | ISBN-10 / ISBN-13 exact match override; paperback vs hardcover validation. |
| `home_appliances` | Amazon, Flipkart, Croma, Vijay Sales | Capacity/energy rating verification; warranty exclusion parsing. |
| `sports` | Decathlon, Amazon, Flipkart | Brand/size exact match; token scoring on authentic gear lines. |
| `automotive` | Amazon, Flipkart, Boodmo | Part number matching; vehicle make/model compatibility cross-checks. |

---

## 4. Security Architecture & Compliance Matrix (SEC-1 to SEC-16)

| Requirement ID | Description | Implementation Details & Code Reference |
|---|---|---|
| **SEC-1** | Multi-tenant organization scoping | All queries filter by `organization_id`. Verified in `agentic_routes.py`, `task_manager.py`, and `test_cross_org_access_forbidden()`. |
| **SEC-2** | Streaming & task ownership isolation | `/task/:id/stream` and `/task/:id/state` reject mismatched `organization_id` with HTTP 403 / `TaskAccessDeniedError`. |
| **SEC-3** | Circuit breaker state protection | Scraper health stored in `ScraperReliability`. Only internal task worker mutations permitted; no client overrides. |
| **SEC-4** | Catalog CSV formula injection defense | `catalog_ingestion_service.py` prepends `'` to any cell beginning with `=`, `+`, `-`, `@`. Enforces 10MB limit. |
| **SEC-5** | LLM prompt injection defense | `base_agent.py` strips control characters, delimits user inputs in XML tags, and sanitizes instructions. |
| **SEC-6** | Database transaction atomicity | `catalog_update_agent.py` wraps catalog price updates, `PriceHistory`, and `AuditLog` in atomic nested transactions. |
| **SEC-7** | Immutable price history ledger | `PriceHistory` has no update or delete routes; entries are append-only. |
| **SEC-8** | Structured audit logging | Every price change logs `user_id`, `task_id`, `before_value`, `after_value`, `ip_address` to `audit_logs`. |
| **SEC-9** | Output sanitization | Agent responses pass through `sanitize_output()` before event bus broadcast and DB serialization. |
| **SEC-10** | Price sanity bounding | Deviations $> 50\%$ trigger `sanity_bound_flagged = True` and block auto-approval. |
| **SEC-11** | Email/Webhook injection defense | Auto-escaped Jinja2 templates in `notification_agent.py` sanitize recipient and dynamic variables. |
| **SEC-12** | Proxy credential masking | `ProxyManager` masks proxy credentials in all logging and exception traces (`user:***@host:port`). |
| **SEC-13** | Rate limiting on recommendation trigger | Rate-limited by org and IP (10 requests/min/org) to prevent DoS against scrapers. |
| **SEC-14** | Ephemeral event bus message retention | Local bus keeps rolling 100-message buffer; Pub/Sub topics configure 24-hour message retention. |
| **SEC-15** | Secrets handling via Secret Manager | Zero plaintext secrets in repo; production uses Google Cloud Secret Manager. |
| **SEC-16** | Principle of least privilege (IAM) | Cloud Run service accounts restricted to Pub/Sub publisher/subscriber and Cloud SQL Client. |

---

## 5. Event Bus & Task State Mechanics

### Pydantic v2 Event Schema (`AgentMessage`)
```python
class AgentMessage(BaseModel):
    model_config = ConfigDict(frozen=True)
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    organization_id: int
    sender_agent: str
    event_type: str
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

### Supported Runtime Modes
1. **Local Development Mode (`EVENT_BUS_PROVIDER=local`)**:
   - Thread-safe in-memory pub/sub (`LocalEventBus`).
   - Per-task rolling subscriber queues with zero-dependency execution.
   - Mock scraper mode (`MOCK_SCRAPING=true`) provides deterministic, realistic competitor price simulations without network locks or CAPTCHAs.
2. **GCP Enterprise Mode (`EVENT_BUS_PROVIDER=pubsub`)**:
   - Google Cloud Pub/Sub topics: `pricing-tasks-topic`, `pricing-events-topic`.
   - Cloud Pub/Sub push/pull subscriptions across horizontally autoscaled Cloud Run microservices.

---

## 6. GCP Production Deployment Architecture

```
                                  [ Internet / Merchant ]
                                             │
                                             ▼
                                  [ Google Cloud Armor ]
                                  (WAF & Rate Limiting)
                                             │
                                             ▼
                                [ Cloud Load Balancing ]
                                             │
                                             ▼
                             [ Cloud Run: Backend / API ]
                                (Zero-Trust VPC Connector)
                                     │               │
                    ┌────────────────┘               └────────────────┐
                    ▼                                                 ▼
        [ Google Cloud Pub/Sub ]                           [ Cloud SQL (Postgres) ]
      (Distributed Task Event Bus)                           (Private IP / IAM Auth)
                    │
                    ▼
       [ Cloud Run: Scraper Worker ] ──(Egress NAT)──> [ Residential Proxy Mesh ]
```

### Production Checklist
1. **Cloud Run Setup**:
   ```bash
   gcloud run deploy pricing-api \
     --image gcr.io/$PROJECT_ID/pricing-backend:latest \
     --vpc-connector pricing-vpc-conn \
     --set-secrets="DATABASE_URL=pricing-db-secret:latest,JWT_SECRET=jwt-secret:latest" \
     --service-account=pricing-api-sa@$PROJECT_ID.iam.gserviceaccount.com \
     --no-allow-unauthenticated
   ```
2. **Cloud Pub/Sub Configuration**:
   ```bash
   gcloud pubsub topics create pricing-events-topic --message-retention-duration=1d
   gcloud pubsub subscriptions create pricing-events-sub --topic=pricing-events-topic --ack-deadline=60
   ```
3. **Cloud SQL Private Service Connect**:
   - Cloud SQL instance configured with private IP only.
   - Cloud Run connects via Serverless VPC Access Connector (`pricing-vpc-conn`).

---

## 7. Verification & Test Evidence

All components have been verified with 12 automated test suites in `backend/tests/test_agentic_system.py`:
- `test_event_bus_org_isolation`: Asserts tenant data never leaks across org boundaries.
- `test_product_match_scoring`: Validates fuzzy/token match algorithms and threshold filtering.
- `test_margin_floor_enforcement`: Confirms code-level margin floor strictly overrides LLM outputs.
- `test_price_sanity_bounds`: Confirms > 50% price swings are flagged for human oversight.
- `test_csv_injection_neutralization`: Confirms formula injection characters (`=`, `+`, `-`, `@`) are escaped.
- `test_cross_org_access_forbidden`: Confirms SEC-2 task access control yields HTTP 403 on tenant mismatch.
- `test_circuit_breaker_tripping`: Confirms consecutive failures open the circuit breaker and bypass targets.
- `test_atomic_catalog_update_and_audit`: Confirms atomic updates and immutable audit logging.
- `test_prompt_injection_sanitization`: Confirms malicious prompt directives are neutralized.
- `test_idempotency_cache`: Confirms duplicate pricing requests return cached runs without redundant scraping.
- `test_search_url_encoding`: Confirms URL encoding (spaces, quotes, commas, parentheses) prevents malformed searches.
- `test_unknown_platform_no_silent_fallback`: Confirms unknown platforms raise explicit `ValueError` without silent cross-platform pollution.

All 12 tests passing with 100% success rate. Frontend builds cleanly with zero TypeScript errors.
