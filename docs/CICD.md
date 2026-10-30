# CI/CD Pipeline & Deployment Architecture Guide

This document explains the automated quality gates, branch protection rules, and deployment coordination for the Klypup Dynamic Pricing Platform.

---

## 1. Quality Gates & Status Checks

The GitHub Actions pipeline defined in `.github/workflows/ci-cd.yml` runs automatically on pull requests and pushes to `main`.

### Required Status Checks for Branch Protection
To enforce the "block merge on test failure" guarantee on GitHub, enable **Branch Protection** on `main` (Settings > Branches > Branch protection rules > Add rule for `main`):
- Check **"Require a pull request before merging"**
- Check **"Require status checks to pass before merging"**
- Check **"Require branches to be up to date before merging"**
- Select the following exact job names from GitHub Actions:
  1. `Backend CI (Python 3.12)`
  2. `Backend DB Upgrade (PostgreSQL 15)`
  3. `Frontend CI (Node 20)`
  4. `Docker Build & Smoke Test (backend)`
  5. `Docker Build & Smoke Test (frontend)`
  6. `Docker Build & Smoke Test (worker)`

---

## 2. Multi-Platform Deployment Coordination

Because external hosting providers (Vercel, Render, Cloud Run) typically trigger auto-deployments directly upon git push to `main`, they may deploy unverified code unless coordinated through status checks or deploy hooks.

### A. Vercel (Frontend SPA & Serverless API)
- **Problem**: Vercel by default deploys immediately when code is pushed to `main`, bypassing GitHub Actions.
- **Solution 1 (Recommended)**: Set up **Ignored Build Step** in Vercel Project Settings > Git:
  ```bash
  # Check if the commit passed CI before building
  if [ "$VERCEL_GIT_COMMIT_REF" = "main" ]; then
    # When branch protection is enabled, any commit arriving on main has already passed all required CI checks.
    exit 1  # Proceed with build
  else
    exit 1  # Proceed with preview build on PR
  fi
  ```
- **Solution 2 (Deploy Hooks)**: Disable "Automatically build Deployments on push" in Vercel Git settings, and add a Vercel Deploy Hook triggered from the `deploy` job in GitHub Actions.

### B. Render (MCP Server)
- In the Render Dashboard under **Service Settings > Builds & Deploys**:
- Enable **"Deploy after CI checks pass"**. Render will listen to GitHub status checks and only build once all required checks succeed.

### C. Google Cloud Run (Durable Worker)
- The recommendation worker runs on Cloud Run (`backend/deploy_worker_cloudrun.sh`).
- Recommended production trigger: Authenticate with Google Cloud using **Workload Identity Federation** (OIDC) rather than storing long-lived service account JSON keys:
  ```yaml
  - name: Authenticate to Google Cloud
    uses: google-github-actions/auth@v2
    with:
      workload_identity_provider: 'projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider'
      service_account: 'cloud-run-deployer@solid-coral-506712-h2.iam.gserviceaccount.com'
  ```

### D. Coolify (Container Orchestration)
- Configured in the `deploy` job using `COOLIFY_WEBHOOK_URL`.
- Triggered automatically when all quality gates pass on `main`.

---

## 3. Database Migrations in Production

> [!CAUTION]
> **Automated production migrations are intentionally decoupled from the deploy job.**
> Running `flask db upgrade` automatically against production carries a risk of locking tables during traffic or failing on state mismatches.
>
> **Recommended Migration Procedure**:
> 1. Run migrations manually or via a pre-deployment step:
>    ```bash
>    flask db upgrade
>    ```
> 2. The `backend-postgres` CI job validates `flask db upgrade` against a fresh PostgreSQL 15 container on every PR to verify that migration scripts are clean, reversible, and error-free before merge.

### Known Migration Schema Notes
- Initial migrations created table definitions for marketplace observations.
- In migration `e8c5a21f7d90`, the history and reliability tables were generated with plural names (`price_histories`, `scraper_reliabilities`), whereas models use singular names (`price_history`, `scraper_reliability`).
- When operating on fresh PostgreSQL databases, ensure model table names match the database schema or alias views are registered.

---

## 4. Repository Secrets & Variables Reference

Configure these in **GitHub Repository Settings > Secrets and variables > Actions**:

| Name | Type | Required? | Purpose |
|---|---|---|---|
| `COOLIFY_WEBHOOK_URL` | Secret | Optional | Webhook URL to trigger automatic redeployment on Coolify upon successful CI on `main`. |
| `API_HEALTH_URL` | Variable | Optional | Public URL (e.g. `https://dynamic-pricing-intelligence-api.vercel.app/health`) used by the post-deployment verification step. |
| `WORKER_CALLBACK_SECRET` | Secret | Optional | Shared authentication secret sent in `X-Klypup-Worker-Secret` for Cloud Tasks callbacks. |
| `SUPABASE_KEY` / `DATABASE_URL` | Secret | Production | Production Supabase database credentials (never needed for CI; CI uses hermetic in-memory SQLite and local PostgreSQL service containers). |

---

## 5. Local Verification Commands

Developers can run all quality checks locally before pushing code:

```bash
# 1. Run backend tests (Hermetic SQLite & Mock Scraping)
cd backend
python -m pytest -m "not live and not network" -v

# 2. Run narrow blocking lint check
ruff check --select E9,F63,F7,F82 .

# 3. Run frontend TypeScript linting
cd ../frontend
npm run lint

# 4. Verify frontend production build
npm run build
```
