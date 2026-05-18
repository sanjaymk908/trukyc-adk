#!/bin/bash
set -e

PROJECT_ID=$(gcloud config get-value project)
REGION="us-central1"
SERVICE_NAME="my-adk-agent"

GOOGLE_API_KEY="${GOOGLE_API_KEY:-AIzaSyAkQcoD5l7K0X9lTtvue2HOtyM92P_fbwQ}"
ANTHROPIC_API_KEY_TRUKYC="${ANTHROPIC_API_KEY_TRUKYC:-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}"
SIMUL8OR_API_KEY="${SIMUL8OR_API_KEY:-96dc3f90d11e48298c5cb67caa5aa5c699778371b7ec40f8a48be5cdd2202962}"
PE_API_KEY="${PE_API_KEY:-pe_IOl1EBV7kSk-9Tzv_rDmXpI9WfNMCxI6k2SzG8A2iLY}"
TRUKYC_RELAY_URL="${TRUKYC_RELAY_URL:-https://trukyc-relay.trusources.workers.dev}"
TRUCLAW_GCS_BUCKET="${TRUCLAW_GCS_BUCKET:-truclaw-state-browser-ml}"

echo "Enabling GCP APIs..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com secretmanager.googleapis.com

echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY,ANTHROPIC_API_KEY_TRUKYC=$ANTHROPIC_API_KEY_TRUKYC,SIMUL8OR_API_KEY=$SIMUL8OR_API_KEY,PE_API_KEY=$PE_API_KEY,TRUKYC_RELAY_URL=$TRUKYC_RELAY_URL,TRUCLAW_GCS_BUCKET=$TRUCLAW_GCS_BUCKET,ADK_APP_NAME=orchestrator" \
  --set-secrets="GOOGLE_SERVICE_ACCOUNT_JSON=truclaw-chat-bot-key:latest"

SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format="value(status.url)")

# always set ADK_BASE_URL to the deployed service URL
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
