# Durable recommendation worker

The API creates a `RecommendationJob` row and dispatches one Google Cloud Task. The worker container polls the same Supabase/PostgreSQL job table with row locks and can also process the Cloud Tasks callback contract. The frontend polls the authenticated recommendation status endpoint and receives durable progress events, marketplace offers, and the final recommendation.

The confirmed deployment target is Google Cloud project `solid-coral-506712-h2`, Cloud Tasks location `asia-south1`, and queue `parthdynamic`. The API callback host is `https://dynamic-pricing-intelligence-api.vercel.app`.

## Required configuration

Set the following values in the Vercel API and worker environments:

- `DATABASE_URL`: the Supabase PostgreSQL connection string.
- `GCP_PROJECT_ID`, `GCP_LOCATION`, and `GCP_QUEUE_NAME`: the Cloud Tasks queue configuration.
- `BACKEND_PUBLIC_URL`: the public API origin used by Cloud Tasks.
- `WORKER_CALLBACK_SECRET`: a randomly generated shared secret. The dispatcher sends it in `X-Klypup-Worker-Secret`, and the callback rejects requests without it.
- Existing AI and Brevo variables required by the current pricing and notification services.

Run the additive Alembic migration `d64a4f3b1a21_durable_recommendation_jobs.py` before enabling production recommendation buttons. Build `Dockerfile.worker` as a separate long-running service with `worker_entry.py` as its command. The service should keep at least one instance available, expose no public application endpoints, and use a least-privileged database/service account.

## Runtime behavior

The API never performs marketplace scraping in the request that the user initiates. It creates a queued job, applies category-aware marketplace routing, and returns HTTP 202. The worker claims queued rows using `FOR UPDATE SKIP LOCKED`, records attempts and heartbeats, emits agent events, persists marketplace offers, and requeues stale jobs after the configured lease interval. The existing local in-process worker is retained only for explicit local/testing mode.

Approval updates the stored `Product.current_price`, creates the existing audited `ApprovalAction`, sends the existing Brevo action notification, and allows the user to download the refreshed catalog through `/api/products/export-csv?format=csv` or `format=xlsx`. The original file on the user’s computer is never silently modified.
