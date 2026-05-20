# TruClaw ADK Guardrail

TruClaw is a biometric security plugin for Google ADK. It intercepts dangerous agent tool calls, classifies them with Gemini, and requires Face ID approval on a paired iPhone before execution — creating a hard gate between an AI agent and any destructive action.

[![TruClaw Demo](https://img.youtube.com/vi/5ROaep5yn1k/maxresdefault.jpg)](https://youtu.be/5ROaep5yn1k)

---

## How It Works

When an agent calls a tool, TruClaw intercepts it, classifies it with Gemini 3.5 Flash, and if dangerous, sends a push notification to your paired iPhone. You approve with Face ID. A Secure Enclave-signed JWT is returned, verified, and the tool executes. If denied or timed out, the tool is blocked. Every decision is appended to an audit ledger in GCS.

Safe tools pass through instantly. Dangerous tools (trades, deletes, emails, shell commands) require biometric approval before execution.

---

## Quick Start (local)

```bash
pip install -e .
export TRUKYC_RELAY_URL="[https://trukyc-relay.trusources.workers.dev](https://trukyc-relay.trusources.workers.dev)"
export GOOGLE_API_KEY="your-google-api-key"
truclaw install
adk web

```

`truclaw install` writes a `.pth` file into the current Python environment so vanilla `adk web` imports `truclaw_adk.autopatch` at interpreter startup. The autopatch wraps every `google.adk.agents.LlmAgent` and installs TruClaw's `before_tool_callback` on all agents.

---

## Deploy to Google Cloud Run

### Prerequisites

* [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed
* GCP project with billing enabled
* Google API key from [Google AI Studio](https://aistudio.google.com/apikey)
* TruClaw iOS app: [App Store](https://apps.apple.com/us/app/truclaw/id6749509039)

### 1. Authenticate

```bash
gcloud auth login your@email.com
gcloud config set project YOUR_PROJECT_ID

```

### 2. Set API keys

Edit `deploy.sh` and fill in your values, or export as env vars before running:

```bash
export GOOGLE_API_KEY="your-google-api-key"
export SIMUL8OR_API_KEY="your-simul8or-api-key"
export PE_API_KEY="your-porteden-api-key"

```

### 3. Deploy

```bash
chmod +x deploy.sh
./deploy.sh

```

On completion you will see:

```text
Deployed: [https://my-adk-agent-xxxx-uc.a.run.app](https://my-adk-agent-xxxx-uc.a.run.app)
Dev UI:   [https://my-adk-agent-xxxx-uc.a.run.app/dev-ui/](https://my-adk-agent-xxxx-uc.a.run.app/dev-ui/)
Pair:     [https://my-adk-agent-xxxx-uc.a.run.app/pair](https://my-adk-agent-xxxx-uc.a.run.app/pair)
Chat:     [https://my-adk-agent-xxxx-uc.a.run.app/chat](https://my-adk-agent-xxxx-uc.a.run.app/chat)

```

### 4. Connect Google Chat (optional)

Go to [console.cloud.google.com](https://console.cloud.google.com) as your Workspace admin account, then navigate to APIs and Services, Google Chat API, Configuration. Set the HTTP endpoint URL to `https://your-service-url/chat`. Save, then open Google Chat and DM your app.

### 5. Pair your iPhone

Send this message to the agent via Google Chat or Dev UI:

```text
pair my TruClaw device

```

Open the pairing link on your iPhone. The TruClaw app completes pairing automatically. Pairing persists to GCS and survives container restarts.

---

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `GOOGLE_API_KEY` | Yes | Google AI Studio key for agents and Gemini safety classifier |
| `TRUKYC_RELAY_URL` | Yes | TruClaw relay endpoint |
| `TRUCLAW_GCS_BUCKET` | No | GCS bucket for persistent state (default: truclaw-state-truclaw-chat-prod) |
| `TRUCLAW_CLASSIFIER_MODEL` | No | Gemini model for safety classification (default: gemini-3.5-flash) |
| `SIMUL8OR_API_KEY` | No | Simul8or key, trading agent only |
| `PE_API_KEY` | No | PortEden key, email agent only |
| `TRUCLAW_STATE_DIR` | No | Local state directory (default: ./.truclaw) |
| `TRUCLAW_ENFORCE` | No | Set to 0 to log without blocking (default: 1) |
| `TRUCLAW_ADMIN_KEY_HASH` | No | SHA256 hash of admin key for admin CLI |

---

## State Persistence

On Cloud Run, all state persists to GCS when `TRUCLAW_GCS_BUCKET` is set.

| File | GCS path | Description |
| --- | --- | --- |
| Paired devices | truclaw/paired.json | Device pairing, survives restarts |
| Security ledger | truclaw/security-ledger.jsonl | Audit trail of all tool calls |
| Agent memory | truclaw/memory.md | Running summary for classifier context |

---

## Admin CLI

The admin CLI manages the security ledger and memory from the command line. Admin commands require `TRUCLAW_ADMIN_KEY`. The raw key is never stored — Cloud Run stores only `TRUCLAW_ADMIN_KEY_HASH`, a SHA256 hash.

### One-time setup

Make the script executable:

```bash
chmod +x admin.sh

```

Choose an admin key and store its hash on Cloud Run:

```bash
export TRUCLAW_ADMIN_KEY="your-secret-key"
./admin.sh setup-key

```

This stores only the SHA256 hash on Cloud Run. Keep the original key safe — it cannot be recovered from the hash.

To persist the hash across future redeploys, generate it and export before running deploy.sh:

```bash
export TRUCLAW_ADMIN_KEY_HASH=$(echo -n "your-secret-key" | sha256sum | awk '{print $1}')
./deploy.sh

```

### Commands

```bash
TRUCLAW_ADMIN_KEY=your-key ./admin.sh view-ledger
TRUCLAW_ADMIN_KEY=your-key ./admin.sh view-memory
TRUCLAW_ADMIN_KEY=your-key ./admin.sh clear-ledger
TRUCLAW_ADMIN_KEY=your-key ./admin.sh clear-memory
TRUCLAW_ADMIN_KEY=your-key ./admin.sh clear-all

```

### What each command does

| Command | Description |
| --- | --- |
| `setup-key` | Hashes TRUCLAW_ADMIN_KEY and stores the hash on Cloud Run. Run once after first deploy. |
| `view-ledger` | Prints recent security events from GCS. Includes tool name, args, danger classification, and outcome. |
| `view-memory` | Prints the classifier memory file from GCS, used for cumulative pattern detection. |
| `clear-ledger` | Deletes the security ledger locally and from GCS. Use before demos or to reset session context. |
| `clear-memory` | Deletes the classifier memory file locally and from GCS. Use when context has become stale. |
| `clear-all` | Clears both ledger and memory in one command. Recommended before demos. |

### How authentication works

When you run an admin command, admin.sh reads `TRUCLAW_ADMIN_KEY_HASH` from the live Cloud Run service, then launches a Cloud Run Job inside the container image with both the hash and your key. `admin_cli.py` hashes the provided key and compares it to the stored hash. Match means the command runs. No match means rejected with an error. Someone with only GCS or Cloud Run console access cannot run admin commands without knowing the original key.

---

## Local CLI Commands

```bash
truclaw install    # install autopatch into current Python environment
truclaw doctor     # check environment and configuration
truclaw status     # show paired devices
truclaw pair       # pair a new iPhone via terminal

```

---

## Local State

Default state is project-local:

```text
./.truclaw/security-ledger.jsonl
./.truclaw/memory.md
./.truclaw/devices/paired.json

```

Pairing shape is OpenClaw-compatible:

```json
{
  "userId:deviceHash": {
    "publicKey": "xxx",
    "apnsToken": "yyy",
    "fcmToken": "fff",
    "platform": "ios",
    "userId": "users_112637529877817175384",
    "pairedAt": "2026-04-22T01:54:38.741Z"
  }
}

```

Override state root:

```bash
export TRUCLAW_STATE_DIR="./.truclaw"

```

---

## Logs

All TruClaw events are prefixed with `[OPENCLAW] TruClaw`. To tail Cloud Run logs:

```bash
gcloud beta run services logs tail my-adk-agent \
  --region us-central1 \
  --project=YOUR_PROJECT_ID \
  --account=your@email.com

```

Key checkpoints to watch:

```text
[autopatch] installed BaseAgent.run_async protector
[protect] attached guardrail agent=...
[guardrail] pre-tool agent=... tool=...
[guardrail] safe-tool bypass tool=...
[guardrail] dangerous action requires phone approval tool=...
[challenge] sending challengeSessionId=...
[challenge] approved challengeSessionId=...
[guardrail] approved; allowing tool=...
[ledger] appended id=... tool=... allowed=True dangerous=True
[gcs] uploaded truclaw/security-ledger.jsonl

```

---

## Test Flow

### 1. Install and start

```bash
pip install -e .
truclaw install
truclaw doctor
adk web

```

### 2. Pair your iPhone

Install the TruClaw iOS app from the [App Store](https://apps.apple.com/us/app/truclaw/id6749509039), then run:

```bash
truclaw pair

```

Or send this in the ADK UI:

```text
pair my TruClaw device

```

### 3. Confirm pairing

```bash
truclaw status
cat ./.truclaw/devices/paired.json

```

### 4. Test safe action (no approval required)

```text
show my positions

```

### 5. Test dangerous action (biometric approval required)

```text
buy NVDA at 100

```

Expected logs:

```text
[OPENCLAW] TruClaw [guardrail] pre-tool ...
[OPENCLAW] TruClaw [guardrail] dangerous action requires phone approval ...
[OPENCLAW] TruClaw [challenge] sending push ...
[OPENCLAW] TruClaw [challenge] approved ...
[OPENCLAW] TruClaw [guardrail] approved; allowing tool=...

```

If approval is denied, expired, or invalid, the tool is blocked and ADK receives:

```text
status: blocked
blocked_by: TruClaw

```

---

## License

MIT

