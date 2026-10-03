# Database Migrations Guide: Klypup Dynamic Pricing Platform

This document catalogs all schema changes across the 13-phase production-hardening and AI-depth upgrade.
While development and CI environments utilize `db.create_all()`, production databases (PostgreSQL) and local development replicas (SQLite) require explicit DDL executions.

---

## Phase 2: Single Floor Definition & State Machine CAS

### 1. `pricing_recommendations.base_price`
Captures the `current_price` of the product at recommendation generation time. Used for optimistic concurrency check (compare-and-swap) during approval execution.

**PostgreSQL:**
```sql
ALTER TABLE pricing_recommendations 
ADD COLUMN IF NOT EXISTS base_price DOUBLE PRECISION NULL;
```

**SQLite:**
```sql
ALTER TABLE pricing_recommendations 
ADD COLUMN base_price REAL;
```

---

### 2. `audit_logs.storefront_sync_status` and `storefront_synced_at`
Records the physical execution / browser-use storefront sync status and timestamp.

**PostgreSQL:**
```sql
ALTER TABLE audit_logs 
ADD COLUMN IF NOT EXISTS storefront_sync_status VARCHAR(32) DEFAULT 'pending',
ADD COLUMN IF NOT EXISTS storefront_synced_at TIMESTAMP WITH TIME ZONE NULL;
```

**SQLite:**
```sql
ALTER TABLE audit_logs 
ADD COLUMN storefront_sync_status VARCHAR(32) DEFAULT 'pending';

ALTER TABLE audit_logs 
ADD COLUMN storefront_synced_at TIMESTAMP;
```

---

### 3. Existing Extra Recommendation Columns Reconciliation
Ensures earlier added columns for guardrails and decisions are reconciled across environments.

**PostgreSQL:**
```sql
ALTER TABLE pricing_recommendations
ADD COLUMN IF NOT EXISTS margin_floor_applied BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS margin_floor_value DOUBLE PRECISION NULL,
ADD COLUMN IF NOT EXISTS sanity_bound_flagged BOOLEAN DEFAULT FALSE NOT NULL,
ADD COLUMN IF NOT EXISTS decided_at TIMESTAMP WITH TIME ZONE NULL,
ADD COLUMN IF NOT EXISTS decided_by VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL;
```

**SQLite:**
```sql
ALTER TABLE pricing_recommendations ADD COLUMN margin_floor_applied BOOLEAN DEFAULT 0;
ALTER TABLE pricing_recommendations ADD COLUMN margin_floor_value REAL;
ALTER TABLE pricing_recommendations ADD COLUMN sanity_bound_flagged BOOLEAN DEFAULT 0;
ALTER TABLE pricing_recommendations ADD COLUMN decided_at TIMESTAMP;
ALTER TABLE pricing_recommendations ADD COLUMN decided_by VARCHAR(36);
```

---

## Upcoming Phases Schema Roadmap

### Phase 6: Circuit Breaker Atomic Locks
- `scraper_reliability.failure_window_started_at` (TIMESTAMP)
- `scraper_reliability.probe_lease_until` (TIMESTAMP)

**PostgreSQL:**
```sql
ALTER TABLE scraper_reliability
ADD COLUMN IF NOT EXISTS failure_window_started_at TIMESTAMP WITH TIME ZONE NULL,
ADD COLUMN IF NOT EXISTS probe_lease_until TIMESTAMP WITH TIME ZONE NULL;
```

**SQLite:**
```sql
ALTER TABLE scraper_reliability ADD COLUMN failure_window_started_at TIMESTAMP;
ALTER TABLE scraper_reliability ADD COLUMN probe_lease_until TIMESTAMP;
```

---

### Phase 9: A/B Testing Simulation Flag
- `ab_tests.is_simulated` (BOOLEAN DEFAULT TRUE NOT NULL)

**PostgreSQL:**
```sql
ALTER TABLE ab_tests
ADD COLUMN IF NOT EXISTS is_simulated BOOLEAN DEFAULT TRUE NOT NULL;
```

**SQLite:**
```sql
ALTER TABLE ab_tests ADD COLUMN is_simulated BOOLEAN DEFAULT 1;
```

---

### Phase 10: Model Telemetry & Observability
- `ai_call_logs.task_id` (VARCHAR(100) NULL)
- `ai_call_logs.provider` (VARCHAR(50) NULL)

**PostgreSQL:**
```sql
ALTER TABLE ai_call_logs
ADD COLUMN IF NOT EXISTS task_id VARCHAR(100) NULL,
ADD COLUMN IF NOT EXISTS provider VARCHAR(50) NULL;
```

**SQLite:**
```sql
ALTER TABLE ai_call_logs ADD COLUMN task_id VARCHAR(100);
ALTER TABLE ai_call_logs ADD COLUMN provider VARCHAR(50);
```
