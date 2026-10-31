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
| `GROQ_API_KEY` | Secret | Optional | Primary Groq API key (Qwen-2.5-Coder-32b) powering the fast self-healing engine. |
| `GROQ_API_KEY_BACKUP` | Secret | Optional | Secondary fallback Groq API key for failover upon HTTP 429 rate limit or quota exhaustion. |
| `DEEPSEEK_API_KEY` | Secret | Optional | DeepSeek API key (`deepseek-chat`) used as secondary failover in the LLM provider tier. |
| `HEAL_BOT_TOKEN` | Secret | Optional | Fine-grained PAT or GitHub App token with `contents: write`, `pull-requests: write`, and `actions: write` permissions. Enables commits pushed by auto-heal to automatically trigger a new CI verification run. If omitted, the harness pushes using `GITHUB_TOKEN` and dispatches `workflow_dispatch` on `ci-cd.yml` via the GitHub REST API. |
| `COOLIFY_WEBHOOK_URL` | Secret | Optional | Webhook URL to trigger automatic redeployment on Coolify upon successful CI on `main`. |
| `API_HEALTH_URL` | Variable | Optional | Public URL (e.g. `https://dynamic-pricing-intelligence-api.vercel.app/health`) used by the post-deployment verification step. |
| `WORKER_CALLBACK_SECRET` | Secret | Optional | Shared authentication secret sent in `X-Klypup-Worker-Secret` for Cloud Tasks callbacks. |
| `SUPABASE_KEY` / `DATABASE_URL` | Secret | Production | Production Supabase database credentials (never needed for CI; CI uses hermetic in-memory SQLite and local PostgreSQL service containers). |

---

## 5. Autonomous Self-Healing Pipeline (DeepSeek / Groq Harness)

When a test failure occurs on a Pull Request:
1. **Safety Trigger Gate**:
   - The `auto-heal` job activates in `.github/workflows/ci-cd.yml` only on failed PRs from the **same repository** (`head.repo.full_name == github.repository`).
   - Untrusted fork PRs are strictly rejected to prevent secret leakage or privileged code execution.
   - Concurrency group `auto-heal-${{ github.event.pull_request.number || github.ref }}` with `cancel-in-progress: false` prevents concurrent job stampedes.
2. **Artifact & Report Ingestion**:
   - Downloads JUnit XML reports from `backend/reports/junit.xml` generated with `junit_family=xunit1` (preserving the `file` attribute).
   - Constructs exact pytest node IDs (`file::Class::test[param]`).
3. **Bot-Verified PR Range Loop Guard**:
   - Inspects git history across the PR range (`origin/${base_ref}..HEAD`).
   - Counts commits carrying `[auto-heal]` or `fix(auto-heal)` where the author is strictly verified as `github-actions[bot]`.
   - Halts immediately if $\ge 2$ bot repairs exist or if `[skip auto-heal]` is present.
4. **Pre-LLM Failure Classification**:
   - **Flaky Probe**: Runs an immediate clean re-run probe of the exact failing node ID under a sanitized environment. If it passes, classifies as `FLAKY` and skips repair.
   - **Infrastructure / Non-Code Filter**: Analyzes the final exception line for network timeouts, connection refused, missing 3rd-party modules, or missing env vars. Classifies as `NON_CODE` and skips repair.
   - **Collection Errors**: Classifies broken module/import collection failures as `COLLECTION_ERROR` and skips repair.
   - Only validated `CODE_BUG` defects proceed to the LLM.
5. **Provider Failover Architecture**:
   - Executes ordered failover: `Groq Key #1 -> Groq Key #2 -> DeepSeek`.
   - Automatically catches HTTP 429 rate limits, quota errors, or 5xx server errors, applying backoff before switching providers.
6. **Strict Patch Safety Policy**:
   - **Allowlist Gate**: Patches are only accepted if their resolved path is inside `backend/app/**`.
   - **Anchored Deny List**: Explicitly rejects `.github/**`, `tools/**`, config files, `.env*`, and root files.
   - **Test File Protection**: Refuses edits to `tests/`, `conftest.py`, or test fixtures (unless explicitly enabled via `--allow-test-edits`, which is off in CI).
   - **Anti-Tampering**: Rejects patches that weaken assertions, remove `assert` statements, add skip markers, or introduce dangerous syscalls (`subprocess`, `eval`, `os.system`).
7. **Two-Stage Verification Gate**:
   - **Stage 1 (Exact Node ID)**: Re-runs the exact failing node ID with a 60s timeout in a scrubbed subprocess environment.
   - **Stage 2 (Regression Suite)**: Runs the hermetic test suite (`pytest -m "not live and not network"`) with a 120s timeout.
   - **Atomic Rollback**: If either stage fails, all modified files are restored byte-for-byte.
8. **Remote Race Safety & CI Re-Triggering**:
   - Queries `git ls-remote` to ensure the remote PR branch HEAD has not moved since the job started. If a developer pushed in the interim, the harness safely aborts without pushing.
   - Never force-pushes.
   - Pushes using `HEAL_BOT_TOKEN` if configured; otherwise pushes with `GITHUB_TOKEN` and triggers `workflow_dispatch` on `ci-cd.yml` via the GitHub REST API so CI genuinely re-runs on the healed commit.
9. **PR Comment & Telemetry**:
   - Posts a structured diagnostic audit comment to the PR with classification, provider used, patched files, and verification status.
   - Sensitive tokens (`gsk_`, `sk-`, `ghp_`, `AKIA`, auth headers) are redacted before posting.
   - Logs complete run telemetry to `reports/heal_metrics.json`.

### Verifying the Harness
The self-healing harness is backed by a 100% hermetic unit and integration test suite:
```bash
cd backend
python -m pytest tests/test_deepseek_harness.py -v
```

### 15-Defect Benchmark Suite (`tools/heal_benchmark/`)
To evaluate autonomous self-healing capabilities against real-world failures without faking or mocking, the repository includes a 15-defect benchmark suite covering off-by-one errors, wrong operators, missing null checks, swapped arguments, bad import names, wrong defaults, and 3 deliberately hard/ambiguous bugs.

To execute the benchmark suite:
```bash
# Validate defect injection, test failures, and byte-for-byte rollbacks:
python tools/heal_benchmark/runner.py --dry-run --all

# Run full evaluation against the live configured LLM provider (requires API keys):
python tools/heal_benchmark/runner.py --all
```

#### Benchmark Results (Reported from `reports/benchmark_results.json`)

- **Defect validation**: 15/15 seeded bugs reproduce a failing test
- **LLM Repair Benchmark**: Not executed in test sandbox (requires live Groq/DeepSeek API keys in environment)
- **Execution Mode**: `dry_run_validation`
- **Average Latency**: 6.52s

| ID | Category | Target File | Test Node | Validated | Fixed (Tests Pass) | Semantically Correct | Policy-Rejected | Latency |
|---|---|---|---|---|---|---|---|---|
| `bug_01_off_by_one` | off_by_one | `security_guardrails.py` | `test_check_sanity_bound` | **YES** | not run | not run | not run | 6.04s |
| `bug_02_wrong_operator` | wrong_operator | `security_guardrails.py` | `test_canonical_margin_floor_units` | **YES** | not run | not run | not run | 6.13s |
| `bug_03_missing_null_check` | missing_null_check | `security_guardrails.py` | `test_sanitize_for_prompt` | **YES** | not run | not run | not run | 6.43s |
| `bug_04_wrong_default` | wrong_default | `security_guardrails.py` | `test_effective_min_margin_pct` | **YES** | not run | not run | not run | 6.19s |
| `bug_05_bad_import_name` | bad_import_name | `price_writer.py` | `test_below_floor_rejection` | **YES** | not run | not run | not run | 5.25s |
| `bug_06_swapped_arguments` | swapped_arguments | `price_writer.py` | `test_sanity_bound_rejection_and_flagging` | **YES** | not run | not run | not run | 6.17s |
| `bug_07_incorrect_rounding` | incorrect_rounding | `price_writer.py` | `test_sanity_override_success` | **YES** | not run | not run | not run | 6.30s |
| `bug_08_wrong_comparison` | wrong_comparison_direction | `price_writer.py` | `test_below_floor_rejection` | **YES** | not run | not run | not run | 6.29s |
| `bug_09_inverted_boolean` | inverted_boolean | `circuit_breaker.py` | `test_parse_and_no_match_errors_do_not_trip_circuit` | **YES** | not run | not run | not run | 6.43s |
| `bug_10_wrong_multiplier` | wrong_operator | `circuit_breaker.py` | `test_circuit_breaker_exponential_backoff_and_half_open` | **YES** | not run | not run | not run | 6.13s |
| `bug_11_missing_dict_fallback` | missing_dict_fallback | `marketplace_normalizer.py` | `test_marketplace_normalizer_standardizes_results` | **YES** | not run | not run | not run | 5.98s |
| `bug_12_broken_regex` | broken_regex | `marketplace_normalizer.py` | `test_marketplace_normalizer_standardizes_results` | **YES** | not run | not run | not run | 6.53s |
| `bug_13_ambiguous_tolerance` | hard_ambiguous | `price_writer.py` | `test_stale_price_optimistic_concurrency` | **YES** | not run | not run | not run | 7.69s |
| `bug_14_inverted_set_logic` | hard_ambiguous | `security_guardrails.py` | `test_assert_no_client_supplied_org_id` | **YES** | not run | not run | not run | 9.01s |
| `bug_15_decay_window_logic` | hard_ambiguous | `circuit_breaker.py` | `test_sliding_window_failure_decay_after_60_minutes` | **YES** | not run | not run | not run | 7.27s |

> **Note**: Benchmark defect validation: 15/15 fixtures verified against existing tests. LLM repair benchmark not executed (no live API keys in test environment; see instructions above to run locally).

---

## 6. Live Demonstration Recipes

### Prerequisites & GitHub Setup
1. **GitHub Secret**: Configure `HEAL_BOT_TOKEN` in Repository Settings > Secrets and variables > Actions with a fine-grained PAT (permissions: `contents: write`, `pull-requests: write`, `actions: write`). If omitted, pushing uses default `GITHUB_TOKEN` and triggers CI re-run via `workflow_dispatch` fallback.
2. **PR Trigger**: PR branch must be pushed to the same repository (`parthTyagi-tech/dynamic-pricing-intelligence-platform`), NOT a fork (fork PRs are strictly rejected for safety).
3. **Concurrency**: Job concurrency group `auto-heal-${{ github.event.pull_request.number || github.ref }}` with `cancel-in-progress: false` ensures runs are never abruptly cancelled.

---

### Recipe 1: End-to-End Autonomous Repair Demo (`test/harness-verification`)

> [!IMPORTANT]
> **STATUS: NOT YET EXECUTED (Live PR pending)**  
> **PR**: None yet (execute steps below manually on GitHub to create live PR)

This recipe demonstrates the complete happy-path lifecycle: a real code defect in a pricing calculation fails CI, triggers the autonomous harness, gets diagnosed and patched strictly inside `backend/app/**`, passes two-stage verification, gets committed by the bot, and triggers a fresh CI run that turns completely green.

#### Step 1: Create a feature branch
```bash
git checkout main
git pull origin main
git checkout -b test/harness-verification
```

#### Step 2: Introduce a real defect into `backend/app/utils/security_guardrails.py`
In `backend/app/utils/security_guardrails.py` (around line 242), modify `compute_price_floor`:
```python
# --- ORIGINAL ---
def compute_price_floor(cost_price: float, min_margin_pct: float) -> float:
    """Canonical price floor: cost * (1 + pct/100). Single source of truth."""
    if cost_price is None or cost_price < 0 or min_margin_pct is None:
        raise ValueError("invalid floor inputs")
    return round(float(cost_price) * (1.0 + float(min_margin_pct) / 100.0), 2)

# --- CORRUPTED DEFECT ---
def compute_price_floor(cost_price: float, min_margin_pct: float) -> float:
    """Canonical price floor: cost * (1 + pct/100). Single source of truth."""
    if cost_price is None or cost_price < 0 or min_margin_pct is None:
        raise ValueError("invalid floor inputs")
    return round(float(cost_price) * (1.0 - float(min_margin_pct) / 100.0), 2)
```
*(This defect subtracts margin percentage instead of adding markup, causing floor prices to compute below product cost).*

#### Step 3: Verify the failure locally
```bash
cd backend
python -m pytest tests/test_price_floor_hypothesis.py::test_canonical_margin_floor_units -v
```
*Expected: Test fails with `AssertionError: assert 58500.0 == 71500.0`.*

#### Step 4: Commit, push, and open PR
```bash
git add backend/app/utils/security_guardrails.py
git commit -m "feat(pricing): adjust baseline margin calculation"
git push origin test/harness-verification
```
Open a Pull Request on GitHub targeting `main` (title: `test: verify autonomous self-healing harness`).

#### Step 5: Expected Live Pipeline Progression
1. **Initial CI Failure**: The `backend-ci` job executes pytest and fails on `test_price_floor_hypothesis.py::test_canonical_margin_floor_units`, generating `backend/reports/junit.xml`.
2. **Auto-Heal Activation**: The `auto-heal` job activates in `.github/workflows/ci-cd.yml`.
   - Verifies same-repository security gate (`head.repo.full_name == github.repository`).
   - Downloads JUnit XML artifact generated with `xunit1`.
   - Constructs exact pytest node ID: `tests/test_price_floor_hypothesis.py::test_canonical_margin_floor_units`.
3. **Pre-LLM Triage**:
   - Runs a clean flaky re-run probe (fails again, proving it is deterministic).
   - Inspects the final exception line (`AssertionError`). Classifies failure as `CODE_BUG`.
4. **LLM Generation & Safety Validation**:
   - Calls the configured provider (Groq Qwen-2.5-Coder-32b with DeepSeek failover).
   - Validates that the patch targets `backend/app/utils/security_guardrails.py` (within allowlist).
   - Verifies zero edits to test files, no removed `assert` lines, and no dangerous syscalls.
5. **Two-Stage Verification Gate**:
   - **Stage 1**: Re-runs the exact failing node ID (`pytest tests/test_price_floor_hypothesis.py::test_canonical_margin_floor_units`) -> **PASSED**.
   - **Stage 2**: Runs full hermetic regression suite (`pytest -m "not live and not network"`) -> **PASSED**.
6. **Commit & Push**:
   - Staged only the patched file (never `git add -A`).
   - Commits as `github-actions[bot]` with message `fix(auto-heal): Invert margin subtraction back to addition [auto-heal]`.
   - Confirms remote branch HEAD has not moved via `git ls-remote` (race condition check).
   - Pushes commit to `test/harness-verification`.
7. **Automated CI Re-run & Green Status**:
   - GitHub Actions automatically re-triggers the workflow on the new commit (powered by `HEAL_BOT_TOKEN` push or `workflow_dispatch` fallback).
   - The subsequent workflow run passes 100% green!
8. **PR Comment Posted**:
   - The bot posts a structured diagnostic summary on the PR with root cause, files patched, provider used, and latency metrics.

---

### Policy Rejections & Flaky/Non-Code Verification (Deterministic Unit Tests)

Rather than relying on non-deterministic live model prompts to simulate policy rejections, all safety guardrails and classification filters are deterministically enforced and verified by hermetic unit tests in `backend/tests/test_deepseek_harness.py`:

- **Disallowed Path Rejections**: Tested by `test_patch_policy_disallowed_paths_and_test_file_edits` and `test_anchored_allowlist_vs_deny_list` (verifies `backend/app/tools/x.py` is allowed while `tools/x.py` and `.github/**` are rejected).
- **Test File Protection & Assertion Weakening**: Tested by `test_assertion_weakening_and_dangerous_calls_rejected` (rejects deleting `assert`, adding skip markers, or invoking eval/exec).
- **Flaky Test Probe**: Tested by `test_flaky_classification_skips_llm` (test passes on clean re-run probe; LLM call skipped; metrics recorded).
- **Non-Code / Infrastructure Failures**: Tested by `test_non_code_classification_skips_llm` and `test_failure_classification_edge_cases` (missing 3rd-party dependencies, network timeouts, and mocked exceptions).
- **Suite Collection Errors**: Tested by `test_collection_error_handling` (broken imports classify as `COLLECTION_ERROR` and skip LLM).

---

## 7. Local Verification Commands

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
