#!/usr/bin/env bash
#
# Deploy the Kriti backend to Cloud Run with the GSC service-account key
# mounted from Secret Manager (so live GSC works on the deployed domain).
#
# The key is NEVER baked into the image. It is stored in Secret Manager and
# mounted into the container at /secrets/gsc_credentials.json at runtime.
#
# Requirements: gcloud CLI, authenticated account (gcloud auth login),
# and the service-account JSON at config/gsc_credentials.json.
#
# Usage:  ./deploy/deploy_cloudrun.sh
set -euo pipefail

PROJECT="${PROJECT:-for-kriti-500207}"
REGION="${REGION:-australia-southeast1}"
SERVICE="${SERVICE:-kriti-maai}"
SECRET_NAME="${SECRET_NAME:-gsc-credentials}"
CREDENTIALS_FILE="${CREDENTIALS_FILE:-config/gsc_credentials.json}"
SITE_URL="${SITE_URL:-https://selfstorage.help/}"
MOUNT_PATH="/secrets/gsc_credentials.json"
# OpenRouter (AI) — key goes into Secret Manager, never baked into the image.
OPENROUTER_SECRET="${OPENROUTER_SECRET:-openrouter-key}"
OPENROUTER_MODEL="${OPENROUTER_MODEL:-nvidia/nemotron-3-super-120b-a12b:free}"
OPENROUTER_KEY="${OPENROUTER_KEY:-}"

[ -f "$CREDENTIALS_FILE" ] || { echo "Credentials file not found: $CREDENTIALS_FILE" >&2; exit 1; }

# Resolve the OpenRouter key from .env if not supplied via env var.
if [ -z "$OPENROUTER_KEY" ] && [ -f ".env" ]; then
  OPENROUTER_KEY="$(grep -E '^\s*OPENROUTER_API_KEY=' .env | head -n1 | sed -E 's/^\s*OPENROUTER_API_KEY=//' | tr -d '[:space:]')"
fi
[ -n "$OPENROUTER_KEY" ] || { echo "OpenRouter key not found. Set OPENROUTER_KEY or OPENROUTER_API_KEY in .env" >&2; exit 1; }

echo "==> Project=$PROJECT Region=$REGION Service=$SERVICE"

echo "==> Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  secretmanager.googleapis.com \
  searchconsole.googleapis.com \
  cloudbuild.googleapis.com \
  --project "$PROJECT"

if ! gcloud secrets describe "$SECRET_NAME" --project "$PROJECT" >/dev/null 2>&1; then
  echo "==> Creating secret $SECRET_NAME..."
  gcloud secrets create "$SECRET_NAME" --replication-policy="automatic" --project "$PROJECT"
fi
echo "==> Adding new secret version from $CREDENTIALS_FILE..."
gcloud secrets versions add "$SECRET_NAME" --data-file="$CREDENTIALS_FILE" --project "$PROJECT"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
echo "==> Granting secret access to runtime SA: $RUNTIME_SA"
gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project "$PROJECT"

# Store the OpenRouter key in Secret Manager and grant the runtime SA access,
# so AI features work on the deployed domain (key is never in the image).
if ! gcloud secrets describe "$OPENROUTER_SECRET" --project "$PROJECT" >/dev/null 2>&1; then
  echo "==> Creating secret $OPENROUTER_SECRET..."
  gcloud secrets create "$OPENROUTER_SECRET" --replication-policy="automatic" --project "$PROJECT"
fi
echo "==> Adding new OpenRouter secret version..."
printf '%s' "$OPENROUTER_KEY" | gcloud secrets versions add "$OPENROUTER_SECRET" --data-file=- --project "$PROJECT"
echo "==> Granting OpenRouter secret access to runtime SA: $RUNTIME_SA"
gcloud secrets add-iam-policy-binding "$OPENROUTER_SECRET" \
  --member="serviceAccount:${RUNTIME_SA}" \
  --role="roles/secretmanager.secretAccessor" \
  --project "$PROJECT"

echo "==> Deploying $SERVICE to Cloud Run..."
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --project "$PROJECT" \
  --allow-unauthenticated \
  --update-secrets="${MOUNT_PATH}=${SECRET_NAME}:latest,OPENROUTER_API_KEY=${OPENROUTER_SECRET}:latest" \
  --set-env-vars="GSC_CREDENTIALS_PATH=${MOUNT_PATH},GSC_SITE_URL=${SITE_URL},OPENROUTER_MODEL=${OPENROUTER_MODEL}"

echo "==> Done. Verify with:"
echo "    curl ${SITE_URL}api/integrations/gsc/status"
echo "    (AI) POST a brief/write request and confirm no '[OpenRouter not configured]' text."
