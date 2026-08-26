#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-solid-coral-506712-h2}"
LOCATION="${GCP_LOCATION:-asia-south1}"
QUEUE="${GCP_QUEUE_NAME:-parthdynamic}"
SERVICE="${WORKER_SERVICE_NAME:-klypup-recommendation-worker}"
IMAGE="${LOCATION}-docker.pkg.dev/${PROJECT_ID}/klypup/${SERVICE}:latest"

: "${BACKEND_PUBLIC_URL:=https://dynamic-pricing-intelligence-api.vercel.app}"
: "${DATABASE_SECRET_NAME:?Set DATABASE_SECRET_NAME to an existing Secret Manager secret name}"
: "${WORKER_CALLBACK_SECRET_NAME:?Set WORKER_CALLBACK_SECRET_NAME to an existing Secret Manager secret name}"

command -v gcloud >/dev/null || { echo "gcloud CLI is required" >&2; exit 1; }
gcloud config set project "$PROJECT_ID" >/dev/null
gcloud services enable cloudtasks.googleapis.com run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

gcloud artifacts repositories describe klypup --location="$LOCATION" >/dev/null 2>&1 || \
  gcloud artifacts repositories create klypup --repository-format=docker --location="$LOCATION" --description="Klypup worker images"

gcloud tasks queues describe "$QUEUE" --location="$LOCATION" >/dev/null 2>&1 || \
  gcloud tasks queues create "$QUEUE" --location="$LOCATION"

gcloud builds submit . --config=cloudbuild.worker.yaml --substitutions="_IMAGE=$IMAGE"

gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$LOCATION" \
  --no-allow-unauthenticated \
  --min-instances=1 \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCP_LOCATION=$LOCATION,GCP_QUEUE_NAME=$QUEUE,BACKEND_PUBLIC_URL=$BACKEND_PUBLIC_URL,FLASK_ENV=production" \
  --set-secrets="DATABASE_URL=${DATABASE_SECRET_NAME}:latest,WORKER_CALLBACK_SECRET=${WORKER_CALLBACK_SECRET_NAME}:latest"

echo "Worker deployed: $SERVICE"
echo "Queue ready: projects/$PROJECT_ID/locations/$LOCATION/queues/$QUEUE"
