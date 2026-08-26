# Klypup implementation checklist

## Authentication and onboarding

Remove mock and hardcoded runtime fallbacks. Verify login and signup use the live API and persist JWT state. Redirect authenticated users with zero products to onboarding/store integration. Support validated CSV/XLSX product uploads tied to the organization and live Shopify, WooCommerce, and custom API/store URL integrations.

## Catalog and category intelligence

Ensure the products screen reads live products and displays SKU, name, brand, category, cost price, current price, margin, inventory, and pricing status. Map product categories to relevant marketplace scraper platforms before recommendation generation.

## Scraping and status

Make recommendation generation asynchronous through the worker/task layer. Provide SSE or polling status updates with timestamped scraper progress. Persist fresh competitor prices in the competitor_prices table.

## Multi-agent recommendations

Implement the Market Agent, Inventory Agent, and Superior Orchestrator Agent flow. Load the LLM provider key from environment variables. Enforce organization minimum-margin and auto-execute constraints. Persist recommended price, confidence, rationale, executive summary, projected volume increase, projected monthly profit lift, and PENDING status.

## HITL approvals and audit

Ensure recommendations expose rationale, market comparison, inventory status, and recommended price. Approve and reject endpoints must update the product or preserve its price, create approval_actions records, and write permanent audit_logs entries visible through the audit-log interface.

## Autopilot and rollback

After an approved execution, schedule or enqueue a 14-day tracking task. Record sales volume, margin, and conversion velocity. Automatically roll back to the previous price when performance falls below baseline, writing APPROVE/ROLLBACK action records and the specified audit message.

## Notifications

On APPROVE, REJECT, AUTO_EXECUTE, and ROLLBACK, send event payloads through configured email and WhatsApp providers. Include event type, product identity, pricing delta, margin change, LLM rationale, competitor benchmark, inventory velocity, and UTC/local timestamps. Do not require provider secrets in source control.

## Deployment readiness

Use PostgreSQL through DATABASE_URL. Ensure worker initialization is compatible with the selected runtime. Load LLM, Twilio, SMTP/SendGrid, Brevo, and other credentials only from environment variables. Serverless deployment must not start unsafe persistent workers; worker behavior must be tested through a controlled local mode or an appropriate persistent worker runtime.

## Verification gate

Before production: run frontend typecheck/build, backend syntax/import checks, database model/migration checks, auth tests, upload/integration tests, scraper accuracy tests, async status tests, LLM orchestration tests using a controlled test provider, approval/rejection/audit tests, rollback tests, notification adapter tests, and a local frontend-backend end-to-end flow. Record unavailable external credentials or services explicitly rather than claiming those paths passed.
