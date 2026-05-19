#!/bin/bash
# =============================================================================
# TruClaw ADK Deploy Script
# =============================================================================
# Deploys the TruClaw ADK agent to Google Cloud Run.
#
# REQUIRED env vars (set before running):
#   GOOGLE_API_KEY              Google AI Studio API key
#   ANTHROPIC_API_KEY_TRUKYC    Anthropic API key for TruClaw classifier
#
# OPTIONAL env vars:
#   SIMUL8OR_API_KEY            Simul8or API key (only needed for trading agent)
#   PE_API_KEY                  PortEden API key (only needed for email agent)
#   TRUKYC_RELAY_URL            TruClaw relay URL
#                               Default: https://trukyc-relay.trusources.workers.dev
#   TRUCLAW_GCS_BUCKET          GCS bucket for TruClaw state persistence
#                               Default: truclaw-state-truclaw-chat-prod
#   TRUCLAW_ADMIN_KEY           Admin key for admin CLI (never stored — used to
#                               generate TRUCLAW_ADMIN_KEY_HASH only)
#   TRUCLAW_ADMIN_KEY_HASH      SHA256 hash of TRUCLAW_ADMIN_KEY (optional)
#                               If not set, run after deploy:
#                                 ./admin.sh setup-key   (optional, admin use only)
#
# USAGE:
#   ./deploy.sh
#
# CUSTOMIZATION (edit variables below to match your deployment):
# =============================================================================
set -e

# ── customization ─────────────────────────────────────────────────────────────
PROJECT_ID="truclaw-chat-prod"      # GCP project ID
REGION="us-central1"                # Cloud Run region
SERVICE_NAME="my-adk-agent"         # Cloud Run service name
# ─────────────────────────────────────────────────────────────────────────────

# ── required API keys ─────────────────────────────────────────────────────────
GOOGLE_API_KEY="${GOOGLE_API_KEY:-your-google-api-key}"
ANTHROPIC_API_KEY_TRUKYC="${ANTHROPIC_API_KEY_TRUKYC:-your-anthropic-api-key}"
# ─────────────────────────────────────────────────────────────────────────────

# ── optional API keys ─────────────────────────────────────────────────────────
# Only needed if using the trading agent
SIMUL8OR_API_KEY="${SIMUL8OR_API_KEY:-your-simul8or-api-key}"

# Only needed if using the email agent
PE_API_KEY="${PE_API_KEY:-your-pe-api-key}"
# ─────────────────────────────────────────────────────────────────────────────

# ── optional config ───────────────────────────────────────────────────────────
TRUKYC_RELAY_URL="${TRUKYC_RELAY_URL:-https://trukyc-relay.trusources.workers.dev}"
TRUCLAW_GCS_BUCKET="${TRUCLAW_GCS_BUCKET:-truclaw-state-truclaw-chat-prod}"

# OPTIONAL: SHA256 hash of your TRUCLAW_ADMIN_KEY for admin CLI access
# Never store the actual key here — only the hash
#
# To set up admin access before deploying:
#   1. Choose your admin key:
#        export TRUCLAW_ADMIN_KEY="your-secret-key"
#   2. Generate hash and export it:
#        export TRUCLAW_ADMIN_KEY_HASH=$(echo -n "$TRUCLAW_ADMIN_KEY" | sha256sum | awk '{print $1}')
#   3. Run deploy:
#        ./deploy.sh
#
# Or skip and configure after deploy (optional):
#   ./admin.sh setup-key
TRUCLAW_ADMIN_KEY_HASH="${TRUCLAW_ADMIN_KEY_HASH:-}"
# ─────────────────────────────────────────────────────────────────────────────

echo "Enabling GCP APIs..."
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com chat.googleapis.com \
  --project=$PROJECT_ID

echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --project=$PROJECT_ID \
  --timeout=3600 \
  --min-instances=1 \
  --no-cpu-throttling \
  --set-env-vars="GOOGLE_API_KEY=$GOOGLE_API_KEY,ANTHROPIC_API_KEY_TRUKYC=$ANTHROPIC_API_KEY_TRUKYC,SIMUL8OR_API_KEY=$SIMUL8OR_API_KEY,PE_API_KEY=$PE_API_KEY,TRUKYC_RELAY_URL=$TRUKYC_RELAY_URL,TRUCLAW_GCS_BUCKET=$TRUCLAW_GCS_BUCKET,ADK_APP_NAME=orchestrator,ADK_BASE_URL=http://localhost:8080,TRUCLAW_ADMIN_KEY_HASH=$TRUCLAW_ADMIN_KEY_HASH"

SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --project=$PROJECT_ID \
  --format="value(status.url)")

echo ""
echo "✅ Deployed: $SERVICE_URL"
echo "🖥  Dev UI:   $SERVICE_URL/dev-ui/"
echo "📱 Pair:     $SERVICE_URL/pair"
echo "💬 Chat:     $SERVICE_URL/chat"
echo ""
echo "ℹ️  Google Chat API endpoint: $SERVICE_URL/chat"
echo "   Update Google Chat API config if URL changed."
echo ""
if [ -z "$TRUCLAW_ADMIN_KEY_HASH" ]; then
  echo "ℹ️  Admin CLI not configured. To enable (optional):"
  echo "   ./admin.sh setup-key"
fi
