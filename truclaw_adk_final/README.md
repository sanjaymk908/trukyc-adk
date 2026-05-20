# TruClaw ADK Guardrail

TruClaw is a biometric security plugin for Google ADK. It intercepts dangerous agent tool calls, classifies them with Gemini, and requires Face ID approval on a paired iPhone before execution — creating a hard gate between an AI agent and any destructive action.

[![TruClaw Demo](https://img.youtube.com/vi/5ROaep5yn1k/maxresdefault.jpg)](https://youtu.be/5ROaep5yn1k)

---

## How It Works

```
Agent tool call
      ↓
TruClaw intercepts (before_tool_callback)
      ↓
Gemini 3.5 Flash classifies danger
      ↓ dangerous?
FCM push → TruClaw iOS app → Face ID
      ↓ approved?
Secure Enclave JWT → relay → verified
      ↓
Tool executes (or is blocked)
      ↓
Audit ledger → GCS
```

Safe tools pass through instantly. Dangerous tools (trades, deletes, emails, shell commands) require biometric approval on your iPhone before execution.

---

## Quick Start (local)

```bash
pip install -e .
export TRUKYC_RELAY_URL="https://trukyc-relay.trusources.workers.dev"
export GOOGLE_API_KEY="your-google-api-key"
truclaw install
adk web
```

`truclaw install` writes a `.pth` file into the current Python environment so vanilla `adk web` imports `truclaw_adk.autopatch` at interpreter startup. The autopatch wraps every `google.adk.agents.LlmAgent` and installs TruClaw's `before_tool_callback` on all agents.

---

## Deploy to Google Cloud Run

### Prerequisites

- [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed
- GCP project with billing enabled
- Google API key from [Google AI Studio](https://aistudio.google.com/apikey)
- TruClaw iOS app: [App Store](https://apps.apple.com/us/app/truclaw/id6749509039)

### 1. Authenticate

```bash
gcloud auth login your@email.com
gcloud config set project YOUR_PROJECT_ID
```

### 2. Set API keys

Edit `deploy.sh` and fill in your values, or export as env vars before running:

```bash
export GOOGLE_API_KEY="your-google-api-key"
export SIMUL8OR_API_KEY="your-simul8or-api-key"   # optional — trading agent only
export PE_API_KEY="your-porteden-api-key"           # optional — email agent only
```

### 3. Deploy

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

### 4. Connect Google Chat (optional)

Go to [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Google Chat API → Configuration:

- **Connection settings:** HTTP endpoint URL
- **HTTP endpoint URL:** `https://your-service-url/chat`

Save, then open Google Chat and DM your app.

### 5. Pair your iPhone

Send this message to the agent (via Google Chat or Dev UI):

```
pair my TruClaw device
```

Open the pairing link on your iPhone. The TruClaw app completes pairing automatically. Pairing persists to GCS and survives container restarts.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Yes | Google AI Studio key — agents + Gemini safety classifier |
| `TRUKYC_RELAY_URL` | Yes | TruClaw relay endpoint |
| `TRUCLAW_GCS_BUCKET` | No | GCS bucket for persistent state (default: `truclaw-state-truclaw-chat-prod`) |
| `TRUCLAW_CLASSIFIER_MODEL` | No | Gemini model for safety classification (default: `gemini-3.5-flash`) |
| `SIMUL8OR_API_KEY` | No | Simul8or key (trading agent only) |
| `PE_API_KEY` | No | PortEden key (email agent only) |
| `TRUCLAW_STATE_DIR` | No | Local state directory (default: `./.truclaw`) |
| `TRUCLAW_ENFORCE` | No | Set to `0` to log without blocking (default: `1`) |
| `TRUCLAW_ADMIN_KEY_HASH` | No | SHA256 hash of admin key for admin CLI |

---

## State Persistence

On Cloud Run, all state persists to GCS when `TRUCLAW_GCS_BUCKET` is set:

| File | GCS path | Description |
|---|---|---|
| Paired devices | `truclaw/paired.json` | Device pairing — survives restarts |
| Security ledger | `truclaw/security-ledger.jsonl` | Audit trail of all tool calls |
| Agent memory | `truclaw/memory.md` | Running summary for classifier context |

---

## Local CLI Commands

```bash
truclaw install    # install autopatch into current Python environment
truclaw doctor     # check environment and configuration
truclaw status     # show paired devices
truclaw pair       # pair a new iPhone via terminal
```

---

## State (local)

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

All TruClaw events are prefixed with `[OPENCLAW] TruClaw`:

```bash
# tail Cloud Run logs
gcloud beta run services logs tail my-adk-agent \
  --region us-central1 \
  --project=YOUR_PROJECT_ID \
  --account=your@email.com
```

Key checkpoints:

```
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

Install the TruClaw iOS app: [App Store](https://apps.apple.com/us/app/truclaw/id6749509039)

```bash
truclaw pair
```

Or in the ADK UI:

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

```
[OPENCLAW] TruClaw [guardrail] pre-tool ...
[OPENCLAW] TruClaw [guardrail] dangerous action requires phone approval ...
[OPENCLAW] TruClaw [challenge] sending push ...
[OPENCLAW] TruClaw [challenge] approved ...
[OPENCLAW] TruClaw [guardrail] approved; allowing tool=...
```

If approval is denied, expired, or invalid:

```json
{"status": "blocked", "blocked_by": "TruClaw"}
```

---

## Admin CLI

The admin CLI manages the security ledger and memory from the command line. Only users with the admin key can run admin commands. The actual key is never stored — only its SHA256 hash is stored on Cloud Run.

### One-time setup

```bash
chmod +x admin.sh
```

Choose your admin key and store its hash on Cloud Run:

```bash
export TRUCLAW_ADMIN_KEY="your-secret-key"
./admin.sh setup-key
```

This generates a SHA256 hash of your key and stores it on Cloud Run. The actual key is never stored anywhere — only the hash. Keep your key safe — it cannot be recovered from the hash.

To persist the hash across future redeploys, generate it and export before deploying:

```bash
export TRUCLAW_ADMIN_KEY_HASH=$(echo -n "your-secret-key" | sha256sum | awk '{print $1}')
./deploy.sh
```

### Commands

```bash
# view recent security ledger events
TRUCLAW_ADMIN_KEY=your-key ./admin.sh view-ledger

# view agent memory file
TRUCLAW_ADMIN_KEY=your-key ./admin.sh view-memory

# clear security ledger only
TRUCLAW_ADMIN_KEY=your-key ./admin.sh clear-ledger

# clear memory only
TRUCLAW_ADMIN_KEY=your-key ./admin.sh clear-memory

# clear both ledger and memory
TRUCLAW_ADMIN_KEY=your-key ./admin.sh clear-all
```

### What each command does

**`setup-key`** — generates a SHA256 hash of your `TRUCLAW_ADMIN_KEY` and stores it on Cloud Run. Run once after first deploy, and again after any deploy that wipes env vars. Requires GCP project admin access.

**`view-ledger`** — prints the last 20 security events from GCS. Each event includes tool name, arguments, danger classification, reason, and whether it was allowed or blocked.

**`view-memory`** — prints the agent's running memory file from GCS, used by the danger classifier for cumulative pattern detection.

**`clear-ledger`** — deletes the security ledger from the container and GCS. The classifier loses cumulative pattern history. Use when resetting a session or before a demo.

**`clear-memory`** — deletes the memory file from the container and GCS. Use when the agent's context has become stale.

**`clear-all`** — clears both ledger and memory in one command. Recommended before a demo or after a test session.

### How authentication works

1. Admin runs `TRUCLAW_ADMIN_KEY=your-key ./admin.sh <command>`
2. `admin.sh` reads `TRUCLAW_ADMIN_KEY_HASH` from the Cloud Run service
3. Passes both to a Cloud Run Job running inside the container
4. `admin_cli.py` hashes the provided key and compares to the stored hash
5. Match → command runs. No match → rejected with error.

Nobody with only GCS or Cloud Run console access can run admin commands without knowing the original key.
```

---

## License

MIT
