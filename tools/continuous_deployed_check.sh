#!/usr/bin/env bash
set -u
FRONTEND="https://dynamic-pricing-intelligence-platform-nrwemhgh0.vercel.app"
BACKEND="https://dynamic-pricing-intelligence-api.vercel.app"
COMMIT="f65cabb462ba934dc9540065728dba4f002f2c3d"
for attempt in 1 2 3; do
  frontend_code=$(curl -sSL -o /tmp/klypup-frontend-check.html -w '%{http_code}' --max-time 20 "$FRONTEND/")
  frontend_ok=false
  grep -qi '<!doctype html>' /tmp/klypup-frontend-check.html && frontend_ok=true
  backend_code=$(curl -sS -o /tmp/klypup-backend-check.json -w '%{http_code}' --max-time 20 "$BACKEND/health")
  backend_ok=false
  grep -q '"status":"healthy"\|"status": "healthy"' /tmp/klypup-backend-check.json && backend_ok=true
  api_deployments=$(gh api repos/parthTyagi-tech/dynamic-pricing-intelligence-platform/deployments --paginate --jq '.[].sha' | grep -c "$COMMIT" || true)
  echo "attempt=${attempt} frontend_http=${frontend_code} frontend_html=${frontend_ok} backend_http=${backend_code} backend_healthy=${backend_ok} matching_deployments=${api_deployments}"
  if [ "$attempt" -lt 3 ]; then sleep 5; fi
done
