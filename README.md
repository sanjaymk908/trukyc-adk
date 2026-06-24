# TruClaw ADK Guardrail

TruClaw is a biometric security guardrail for Google ADK agents. It intercepts dangerous tool calls before execution, classifies them with Gemini, and requires Face ID approval on a paired iPhone — creating a hard, unbypassable gate between an AI agent and any destructive action.

[![TruClaw Demo](https://img.youtube.com/vi/5ROaep5yn1k/maxresdefault.jpg)](https://youtu.be/5ROaep5yn1k)

---

## How It Works

When an agent calls a tool, TruClaw intercepts it via `before_tool_callback`, classifies it with Gemini Flash, and if dangerous, sends an APNS push notification to your paired iPhone. The notification shows exactly what the agent is trying to do — the tool name, key arguments, and a one-sentence description. You approve with Face ID. A Secure Enclave-signed JWT is returned, verified server-side, and the tool executes. If denied or timed out, the tool is blocked.

Safe tools pass through instantly. Every decision — approved, blocked, or bypassed — is appended to an immutable audit ledger in GCS.

**Monitor mode:** set `TRUCLAW_ENFORCE=0` to log and classify all tool calls without sending challenges. Use this to observe agent behavior and build confidence before turning enforcement on.

---

## Quick Start (local)

### Prerequisites

- Python 3.10+
- [Google ADK](https://github.com/google/adk-python)
- Google API key from [Google AI Studio](https://aistudio.google.com/apikey) (for Gemini classifier)
- TruClaw iOS app: [App Store](https://apps.apple.com/us/app/truclaw/id6749509039)

### 1. Install

```bash
git clone https://github.com/sanjaymk908/trukyc-adk.git
cd trukyc-adk
pip install -e truclaw_adk_final/
```

### 2. Configure environment

```bash
export GOOGLE_API_KEY="your-google-ai-studio-key"
export TRUKYC_RELAY_URL="https://trukyc-relay.trusources.workers.dev"
export TRUCLAW_GCS_BUCKET="your-gcs-bucket-name"   # optional; omit for local-only state
export TRUCLAW_ENFORCE=1                             # set to 0 for monitor+log mode
```

### 3. Install autopatch and start

```bash
truclaw install   # writes .pth into current Python env — runs once per virtualenv
truclaw doctor    # verify config and connectivity
adk web           # autopatch activates at interpreter startup
```

`truclaw install` writes a `.pth` file into the active Python environment so `truclaw_adk.autopatch` is imported at interpreter startup. The autopatch monkey-patches `BaseAgent.run_async` and installs `before_tool_callback` on every agent — no changes to agent code required.

### 4. Set your policy

TruClaw loads its policy from GCS at startup. A default policy is bootstrapped automatically on first run. To customize, edit the policy file in GCS:

```
gs://<TRUCLAW_GCS_BUCKET>/truclaw/policies/<agentId>/TruClaw-Policies.json
```

See [TruClaw-Policies.template.json](truclaw_adk_final/truclaw_adk/TruClaw-Policies.template.json) for the full schema including `safeTools`, `alwaysDangerousTools`, `toolThresholds` (rate limiting), and `businessRules` (LLM behavioral contract).

### 5. Pair your iPhone

```bash
truclaw pair
```

Or send `pair my TruClaw device` in the ADK Dev UI. Open the pairing link on your iPhone — the TruClaw app completes pairing automatically. Pairing state persists to GCS and survives container restarts.

### 6. Test

Trigger a safe action (passes through silently):
```
list open tickets
```

Trigger a dangerous action (sends APNS challenge to your iPhone):
```
create a P0 ticket for the auth service outage
```

Expected log output:
```
[guardrail] pre-tool agent=software_assistant tool=create_new_ticket
[guardrail] dangerous action requires phone approval tool=create_new_ticket
[challenge] sending challengeSessionId=abc123 actionTitle=Create P0 ticket
[challenge] approved challengeSessionId=abc123
[guardrail] approved; allowing tool=create_new_ticket
```

---

## Deploy to Google Cloud Run

### Prerequisites

- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated
- GCP project with billing enabled
- GCS bucket created for TruClaw state
- Google API key from [Google AI Studio](https://aistudio.google.com/apikey)
- TruClaw iOS app: [App Store](https://apps.apple.com/us/app/truclaw/id6749509039)

### 1. Authenticate

```bash
gcloud auth login your@email.com
gcloud config set project YOUR_PROJECT_ID
```

### 2. Create a GCS bucket for TruClaw state

```bash
gcloud storage buckets create gs://truclaw-state-YOUR_PROJECT_ID \
  --project=YOUR_PROJECT_ID \
  --location=us-central1
```

### 3. Set required environment variables

```bash
export GOOGLE_API_KEY="your-google-ai-studio-key"
export TRUCLAW_GCS_BUCKET="truclaw-state-YOUR_PROJECT_ID"
export TRUKYC_RELAY_URL="https://trukyc-relay.trusources.workers.dev"
```

Optional — only needed for specific bundled agents:
```bash
export SIMUL8OR_API_KEY="your-simul8or-key"   # trading agent
export PE_API_KEY="your-porteden-key"          # email agent
```

Optional — for admin CLI access:
```bash
export TRUCLAW_ADMIN_KEY_HASH=$(echo -n "your-secret-admin-key" | sha256sum | awk '{print $1}')
```

### 4. Edit deploy.sh

Open `deploy.sh` and set `PROJECT_ID`, `REGION`, and `SERVICE_NAME` at the top:

```bash
PROJECT_ID="your-project-id"
REGION="us-central1"
SERVICE_NAME="my-adk-agent"
```

### 5. Deploy

```bash
chmod +x deploy.sh
./deploy.sh
```

On completion:
```
✅ Deployed: https://my-adk-agent-xxxx-uc.a.run.app
🖥  Dev UI:   https://my-adk-agent-xxxx-uc.a.run.app/dev-ui/
📱 Pair:     https://my-adk-agent-xxxx-uc.a.run.app/pair
💬 Chat:     https://my-adk-agent-xxxx-uc.a.run.app/chat
```

### 6. Grant IAM permissions

The Cloud Run service account needs read/write access to your GCS bucket:

```bash
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format="value(projectNumber)")
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud storage buckets add-iam-policy-binding gs://truclaw-state-YOUR_PROJECT_ID \
  --member="serviceAccount:${SA}" \
  --role="roles/storage.objectAdmin"
```

### 7. Pair your iPhone

Open `https://your-service-url/pair` on your iPhone or send `pair my TruClaw device` in the Dev UI.

### 8. Connect Google Chat (optional)

In [Cloud Console](https://console.cloud.google.com) → APIs & Services → Google Chat API → Configuration, set the HTTP endpoint to `https://your-service-url/chat`. DM your app in Google Chat.

---

## Policy and Rate Limiting

TruClaw loads a per-agent policy from GCS on startup. The policy controls which tools auto-approve, always escalate, or go through the Gemini classifier, and sets per-tool rate limits.

```jsonc
{
  "agentId": "my_agent",
  "safeTools": ["search_tickets", "get_ticket_by_id", "web_search"],
  "alwaysDangerousTools": ["send_email", "delete_repository"],
  "unclassified": ["create_new_ticket", "update_ticket_priority"],
  "toolThresholds": {
    "create_new_ticket": {
      "dailyLimit": 10,      // per user per day — counted by cron aggregator
      "weeklyLimit": 40
    },
    "update_ticket_priority": {
      "field": "priority",
      "safeBelow": "P1 - High",  // auto-approve P2/P3; escalate P0/P1
      "dailyLimit": 20
    },
    "push_files": {
      "dailyLimit": 0            // always escalate — first call triggers APNS
    }
  },
  "businessRules": "Describe expected agent behavior here. The Gemini classifier uses this as a behavioral contract to discriminate legitimate actions from drift or injection."
}
```

Rate limiting uses two mechanisms: `safeBelow` checks a single field value in the current call's args; `dailyLimit`/`weeklyLimit` check pre-aggregated cumulative counts from `usage_summary.json` in GCS, written by the `cron_aggregator` Cloud Run Job.

Policy path: `gs://<TRUCLAW_GCS_BUCKET>/truclaw/policies/<agentId>/TruClaw-Policies.json`

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Yes | Google AI Studio key — used for Gemini safety classifier |
| `TRUKYC_RELAY_URL` | Yes | TruClaw APNS relay endpoint |
| `TRUCLAW_GCS_BUCKET` | Recommended | GCS bucket for state, policy, and ledger persistence |
| `TRUCLAW_ENFORCE` | No | `1` = block dangerous tools (default). `0` = monitor+log only, no challenges sent |
| `TRUCLAW_CLASSIFIER_MODEL` | No | Gemini model for classification (default: `gemini-2.5-flash`) |
| `TRUCLAW_STATE_DIR` | No | Local state directory (default: `./.truclaw`) |
| `TRUCLAW_ADMIN_KEY_HASH` | No | SHA256 hash of admin key for admin CLI |
| `SIMUL8OR_API_KEY` | No | Simul8or key — trading agent only |
| `PE_API_KEY` | No | PortEden key — email agent only |

---

## State Persistence

All state persists to GCS when `TRUCLAW_GCS_BUCKET` is set. Survives container restarts and redeploys.

| File | GCS path | Description |
|---|---|---|
| Paired devices | `truclaw/paired.json` | Device pairing state |
| Security ledger | `truclaw/security-ledger.jsonl` | Immutable audit trail of all tool calls |
| Agent memory | `truclaw/memory.md` | Cross-session behavioral summary for classifier context |
| Agent policy | `truclaw/policies/<agentId>/TruClaw-Policies.json` | Per-agent enforcement policy |
| Usage summary | `truclaw/policies/<agentId>/usage_summary.json` | Pre-aggregated tool call counts for rate limiting |

---

## Admin CLI

Manages the security ledger and memory from the command line. Requires `TRUCLAW_ADMIN_KEY`.

```bash
chmod +x admin.sh

# One-time setup: store key hash on Cloud Run
export TRUCLAW_ADMIN_KEY="your-secret-key"
./admin.sh setup-key

# Commands
TRUCLAW_ADMIN_KEY=your-key ./admin.sh view-ledger
TRUCLAW_ADMIN_KEY=your-key ./admin.sh view-memory
TRUCLAW_ADMIN_KEY=your-key ./admin.sh clear-ledger
TRUCLAW_ADMIN_KEY=your-key ./admin.sh clear-memory
TRUCLAW_ADMIN_KEY=your-key ./admin.sh clear-all
```

The raw key is never stored — Cloud Run stores only the SHA256 hash. To persist across redeploys:

```bash
export TRUCLAW_ADMIN_KEY_HASH=$(echo -n "your-secret-key" | sha256sum | awk '{print $1}')
./deploy.sh
```

---

## Local CLI Commands

```bash
truclaw install    # write autopatch .pth into current Python env (run once per venv)
truclaw doctor     # check environment, config, and relay connectivity
truclaw status     # show paired devices
truclaw pair       # pair a new iPhone via terminal
```

---

## Logs

All TruClaw events are prefixed `[OPENCLAW] TruClaw`. To tail Cloud Run logs:

```bash
gcloud beta run services logs tail my-adk-agent \
  --region us-central1 \
  --project=YOUR_PROJECT_ID
```

Key log checkpoints:

```
[autopatch] installed BaseAgent.run_async protector
[policy] loaded agentId=... version=... safe=N dangerous=N unclassified=N
[guardrail] pre-tool agent=... agentId=... tool=... userId=...
[guardrail] safe-tool bypass tool=...
[guardrail] threshold safe-bypass tool=...          ← safeBelow triggered
[guardrail] threshold violation: tool=... exceeds dailyLimit=...
[guardrail] dangerous action requires phone approval tool=...
[challenge] sending challengeSessionId=... actionTitle=...
[challenge] approved challengeSessionId=...
[guardrail] approved; allowing tool=...
[guardrail] blocked tool=... reason=approval timeout
[ledger] appended id=... tool=... allowed=True dangerous=True
[gcs] uploaded truclaw/security-ledger.jsonl
```

---

## License

MIT
