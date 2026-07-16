# Phase 1: Supabase Migration Blueprint

## Objective
Replace the standard "Render PostgreSQL" database and custom JWT authentication with Supabase to provide real-time database subscriptions and enterprise-grade authentication.

## Changes Required

### 1. `docker-compose.yml`
*   **Action:** Add the local Supabase stack (Kong, Auth, REST, Realtime, DB) to the `docker-compose.yml` for local development.
*   **Result:** Developers can run `docker-compose up` and have a full Supabase instance running locally mirroring production.

### 2. `backend/models.py`
*   **Action:** No major ORM changes needed, as SQLAlchemy connects to Supabase's Postgres just like any standard Postgres database.
*   **Change:** Ensure the `SQLALCHEMY_DATABASE_URI` reads from the Supabase connection string format.

### 3. `backend/app.py` & Auth Middleware
*   **Action:** Replace the custom JWT validation middleware with the official Supabase Python client.
*   **Change:**
```python
from supabase import create_client, Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Inside middleware:
user = supabase.auth.get_user(token)
```

### 4. `frontend/src/services/api.js`
*   **Action:** Install `@supabase/supabase-js`. Replace standard Axios auth headers with Supabase client calls.
*   **Result:** The frontend will now natively support real-time subscriptions, so when a price is updated by the Orchestrator, the React dashboard updates instantly without a page refresh.

## Expected Outcome
The application will be far more robust and secure, offloading user management and auth to Supabase, and unlocking real-time UI updates for pricing changes.
