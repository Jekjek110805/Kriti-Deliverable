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
SITE_URL="${SITE_URL:-https://kriti-maai-268992122217.australia-southeast1.run.app/}"
MOUNT_PATH="/secrets/gsc_credentials.json"

[ -f "$CREDENTIALS_FILE" ] || { echo "Credentials file not found: $CREDENTIALS_FILE" >&2; exit 1; }

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

echo "==> Deploying $SERVICE to Cloud Run..."
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --project "$PROJECT" \
  --allow-unauthenticated \
  --update-secrets="${MOUNT_PATH}=${SECRET_NAME}:latest" \
  --set-env-vars="GSC_CREDENTIALS_PATH=${MOUNT_PATH},GSC_SITE_URL=${SITE_URL}"

echo "==> Done. Verify with:"
echo "    curl ${SITE_URL}api/integrations/gsc/status"
