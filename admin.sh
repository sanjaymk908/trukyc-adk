#!/bin/bash
# =============================================================================
# TruClaw Admin CLI
# =============================================================================
# Remote admin tool for managing TruClaw state on Cloud Run.
# Runs commands inside the deployed container via Cloud Run Jobs.
#
# SETUP (one-time, run by GCP project admin):
#   1. Choose your admin key:
#        export TRUCLAW_ADMIN_KEY="your-secret-key"
#   2. Store hash on Cloud Run:
#        ./admin.sh setup-key
#
# USAGE (day-to-day, by admin):
#   TRUCLAW_ADMIN_KEY=your-key ./admin.sh view-ledger
#   TRUCLAW_ADMIN_KEY=your-key ./admin.sh view-memory
#   TRUCLAW_ADMIN_KEY=your-key ./admin.sh clear-ledger
#   TRUCLAW_ADMIN_KEY=your-key ./admin.sh clear-memory
#   TRUCLAW_ADMIN_KEY=your-key ./admin.sh clear-all
#
# REQUIRED env vars:
#   TRUCLAW_ADMIN_KEY       The admin key — passed at runtime, never stored
#
# OPTIONAL env vars:
#   TRUCLAW_GCS_BUCKET      GCS bucket for TruClaw state
#                           Default: truclaw-state-truclaw-chat-prod
# =============================================================================
set -e

# ── customization — edit these to match your deployment ──────────────────────
PROJECT_ID="truclaw-chat-prod"                         # GCP project
REGION="us-central1"                                   # Cloud Run region
SERVICE_NAME="my-adk-agent"                            # Cloud Run service name
JOB_NAME="truclaw-admin"                               # Cloud Run job name
GCLOUD="/usr/local/share/google-cloud-sdk/bin/gcloud"  # path to gcloud binary
GCLOUD_ACCOUNT="sanjay@truclawai.com"                  # GCP account to use
GCS_BUCKET="truclaw-state-truclaw-chat-prod"           # GCS bucket
# ─────────────────────────────────────────────────────────────────────────────

TRUCLAW_ADMIN_KEY="${TRUCLAW_ADMIN_KEY:-}"
TRUCLAW_GCS_BUCKET="${TRUCLAW_GCS_BUCKET:-$GCS_BUCKET}"

COMMAND="${1:-help}"

if [ "$COMMAND" = "help" ]; then
  echo "Usage: TRUCLAW_ADMIN_KEY=your-key ./admin.sh <command>"
  echo ""
  echo "Commands:"
  echo "  setup-key       Store admin key hash on Cloud Run (run once)"
  echo "  view-ledger     View recent ledger events"
  echo "  view-memory     View memory file"
  echo "  clear-ledger    Clear security ledger"
  echo "  clear-memory    Clear memory file"
  echo "  clear-all       Clear ledger and memory"
  exit 0
fi

# setup-key: generate hash and store on Cloud Run
if [ "$COMMAND" = "setup-key" ]; then
  if [ -z "$TRUCLAW_ADMIN_KEY" ]; then
    read -s -p "Enter TRUCLAW_ADMIN_KEY to store: " TRUCLAW_ADMIN_KEY
    echo ""
  fi
  if command -v sha256sum &>/dev/null; then
    HASH=$(echo -n "$TRUCLAW_ADMIN_KEY" | sha256sum | awk '{print $1}')
  else
    HASH=$(echo -n "$TRUCLAW_ADMIN_KEY" | shasum -a 256 | awk '{print $1}')
  fi
  echo "Storing hash on Cloud Run..."
  $GCLOUD run services update $SERVICE_NAME \
    --region $REGION \
    --project=$PROJECT_ID \
    --update-env-vars="TRUCLAW_ADMIN_KEY_HASH=$HASH" \
    --account=$GCLOUD_ACCOUNT
  echo "✅ Admin key hash stored. Keep your key safe — it cannot be recovered."
  exit 0
fi

# all other commands require TRUCLAW_ADMIN_KEY
if [ -z "$TRUCLAW_ADMIN_KEY" ]; then
  read -s -p "Enter TRUCLAW_ADMIN_KEY: " TRUCLAW_ADMIN_KEY
  echo ""
fi

echo "Getting image..."
IMAGE=$($GCLOUD run services describe $SERVICE_NAME \
  --region $REGION \
  --project=$PROJECT_ID \
  --format='value(spec.template.spec.containers[0].image)')

echo "Running admin command: $COMMAND"

ENV_VARS="TRUCLAW_ADMIN_KEY=$TRUCLAW_ADMIN_KEY,TRUCLAW_GCS_BUCKET=$TRUCLAW_GCS_BUCKET"

# delete old job to avoid conflicts then recreate
$GCLOUD run jobs delete $JOB_NAME \
  --region $REGION \
  --project=$PROJECT_ID \
  --quiet 2>/dev/null || true

$GCLOUD run jobs create $JOB_NAME \
  --image $IMAGE \
  --region $REGION \
  --project=$PROJECT_ID \
  --set-env-vars="$ENV_VARS" \
  --command=python3 \
  --args="-m,truclaw_adk.admin_cli,$COMMAND" \
  --execute-now \
  --wait

echo ""
echo "Fetching logs..."
$GCLOUD logging read \
  "resource.type=cloud_run_job AND resource.labels.job_name=$JOB_NAME" \
  --project=$PROJECT_ID \
  --limit=20 \
  --format="value(textPayload)" \
  --freshness=5m
