#!/bin/bash
set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
SERVICE_NAME="my-adk-agent"

: "${GOOGLE_API_KEY:?Need GOOGLE_API_KEY}"
: "${ANTHROPIC_API_KEY_TRUKYC:?Need ANTHROPIC_API_KEY_TRUKYC}"
: "${SIMUL8OR_API_KEY:?Need SIMUL8OR_API_KEY}"
TRUKYC_RELAY_URL="${TRUKYC_RELAY_URL:-https://trukyc-relay.trusources.workers.dev}"

echo "Enabling GCP APIs..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY,ANTHROPIC_API_KEY_TRUKYC=$ANTHROPIC_API_KEY_TRUKYC,SIMUL8OR_API_KEY=$SIMUL8OR_API_KEY,TRUKYC_RELAY_URL=$TRUKYC_RELAY_URL"

SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format="value(status.url)")
echo ""
echo "✅ Deployed: $SERVICE_URL"
echo "🖥  Dev UI:   $SERVICE_URL/dev-ui/"
