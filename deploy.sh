#!/bin/bash
set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
SERVICE_NAME="my-adk-agent"

GOOGLE_API_KEY="${GOOGLE_API_KEY:-your-google-api-key}"
ANTHROPIC_API_KEY_TRUKYC="${ANTHROPIC_API_KEY_TRUKYC:-your-anthropic-api-key}"
SIMUL8OR_API_KEY="${SIMUL8OR_API_KEY:-your-simul8or-api-key}"
PE_API_KEY="${PE_API_KEY:-your-pe-api-key}"
TRUKYC_RELAY_URL="${TRUKYC_RELAY_URL:-https://trukyc-relay.trusources.workers.dev}"
TRUCLAW_GCS_BUCKET="${TRUCLAW_GCS_BUCKET:-truclaw-state-browser-ml}"

echo "Enabling GCP APIs..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com chat.googleapis.com

echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY,ANTHROPIC_API_KEY_TRUKYC=$ANTHROPIC_API_KEY_TRUKYC,SIMUL8OR_API_KEY=$SIMUL8OR_API_KEY,PE_API_KEY=$PE_API_KEY,TRUKYC_RELAY_URL=$TRUKYC_RELAY_URL,TRUCLAW_GCS_BUCKET=$TRUCLAW_GCS_BUCKET,ADK_APP_NAME=orchestrator"

SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format="value(status.url)")

gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --update-env-vars="ADK_BASE_URL=$SERVICE_URL"

echo ""
echo "✅ Deployed: $SERVICE_URL"
echo "🖥  Dev UI:   $SERVICE_URL/dev-ui/"
echo "📱 Pair:     $SERVICE_URL/pair"
echo ""
echo "ℹ️  ADK_BASE_URL has been set to: $SERVICE_URL"
echo "   To update manually if needed:"
echo "   gcloud run services update $SERVICE_NAME --region $REGION --update-env-vars=\"ADK_BASE_URL=$SERVICE_URL\""
