#!/usr/bin/env bash
# Build and deploy the controller to Cloud Run.
# Reads Secret Manager *names* only — secret values never appear in git or this script.
set -euo pipefail

PROJECT="${PROJECT:-firewall-ai}"
REGION="${REGION:-northamerica-northeast2}"
SERVICE="${SERVICE:-firewall-ai-controller}"
ENROLLMENT_SECRET="${ENROLLMENT_SECRET:-enrollment-key}"
ADMIN_SECRET="${ADMIN_SECRET:-admin-token}"
OFFLINE_AFTER_SEC="${OFFLINE_AFTER_SEC:-120}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Deploying ${SERVICE} to ${PROJECT} in ${REGION}"

gcloud config set project "${PROJECT}"

gcloud run deploy "${SERVICE}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --source="${ROOT}/controller" \
  --allow-unauthenticated \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3 \
  --timeout=60 \
  --set-env-vars="STORE_BACKEND=firestore,GCP_PROJECT=${PROJECT},OFFLINE_AFTER_SEC=${OFFLINE_AFTER_SEC}" \
  --set-secrets="ENROLLMENT_KEY=${ENROLLMENT_SECRET}:latest,ADMIN_TOKEN=${ADMIN_SECRET}:latest"

echo
echo "Service URL:"
gcloud run services describe "${SERVICE}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --format='value(status.url)'
