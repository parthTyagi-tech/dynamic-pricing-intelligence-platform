# Phase 5: Coolify Deployment Blueprint

## Objective
Migrate hosting away from Vercel (Frontend) and Render (Backend) into a self-hosted environment managed entirely by Coolify, providing Enterprise clients with single-tenant data isolation on their own AWS/DigitalOcean infrastructure.

## Changes Required

### 1. `coolify.yaml` or Nixpacks Configuration
*   **Action:** Add the necessary configuration files for Coolify to understand the monorepo structure.
*   **Change:** Coolify uses Nixpacks by default. We will ensure the `backend/requirements.txt` and `frontend/package.json` are correctly structured for auto-detection, or we will write a `docker-compose.yml` specifically tuned for Coolify deployments.

### 2. Infrastructure Consolidation
*   **Action:** Stop deploying the frontend and backend to separate cloud providers.
*   **Change:** Use Coolify to deploy the React Frontend, the Flask Backend, the Supabase instance, the Langflow container, and the Crawl4AI worker all onto the same VPS instance. 
*   **Benefit:** Zero internal latency between the API and the database, and massive cost savings compared to paying multiple cloud providers.

## Expected Outcome
Klypup will have a "Push to Deploy" PaaS that they fully own. When a new Enterprise client signs up, Klypup can spin up an entirely isolated stack on a fresh AWS EC2 instance in minutes using Coolify, guaranteeing zero data mixing between clients.
