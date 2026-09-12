#!/usr/bin/env bash
# One-time GCP bootstrap for project firewall-ai.
# Creates APIs, Firestore, Secret Manager *names*, and IAM.
# You will be prompted for secret values; they are not echoed or stored in git.
set -euo pipefail

PROJECT="${PROJECT:-firewall-ai}"
REGION="${REGION:-northamerica-northeast2}"
ENROLLMENT_SECRET="${ENROLLMENT_SECRET:-enrollment-key}"
ADMIN_SECRET="${ADMIN_SECRET:-admin-token}"

echo "Using project ${PROJECT}, region ${REGION} (Toronto)"
gcloud config set project "${PROJECT}"

echo "Enabling APIs…"
gcloud services enable \
  run.googleapis.com \
  firestore.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com

if gcloud firestore databases describe --database='(default)' >/dev/null 2>&1; then
  echo "Firestore (default) already exists"
else
  echo "Creating Firestore Native database in ${REGION}…"
  gcloud firestore databases create \
    --database='(default)' \
    --location="${REGION}" \
    --type=firestore-native
fi

create_secret() {
  local name="$1"
  local prompt="$2"
  if gcloud secrets describe "${name}" >/dev/null 2>&1; then
    echo "Secret ${name} already exists (not modified)"
    return
  fi
  echo
  echo "${prompt}"
  echo -n "Value (input hidden): "
  read -r -s value
  echo
  if [[ -z "${value}" ]]; then
    echo "empty value — skipping ${name}" >&2
    return 1
  fi
  printf '%s' "${value}" | gcloud secrets create "${name}" --data-file=-
  unset value
}

create_secret "${ENROLLMENT_SECRET}" "Create class enrollment key (students put this in ENROLLMENT_KEY)."
create_secret "${ADMIN_SECRET}" "Create instructor ADMIN_TOKEN (dashboard + /v1/labs)."

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT}" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Granting Cloud Run runtime SA Firestore + Secret Manager access…"
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/datastore.user" \
  --condition=None >/dev/null

gcloud secrets add-iam-policy-binding "${ENROLLMENT_SECRET}" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" >/dev/null

gcloud secrets add-iam-policy-binding "${ADMIN_SECRET}" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" >/dev/null

echo
echo "Setup complete. Next: ./infra/deploy.sh"
echo "Runtime service account: ${RUNTIME_SA}"
