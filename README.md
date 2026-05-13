# TruClaw ADK Guardrail

TruClaw is a security plugin for Google ADK that intercepts sensitive tool calls, performs risk classification, and requires out-of-band human approval on a paired iPhone before execution. It adds human-in-the-loop approval, biometric verification, and execution guardrails for shell commands, network actions, and other sensitive tool calls.
[![TruClaw Demo](https://img.youtube.com/vi/5ROaep5yn1k/maxresdefault.jpg)](https://youtu.be/5ROaep5yn1k)

No-code-ish ADK protection flow:
```bash
pip install -e .
export TRUKYC_RELAY_URL="https://trukyc-relay.trusources.workers.dev"
export ANTHROPIC_API_KEY_TRUKYC="..."
truclaw install
adk web
```
`truclaw install` writes a `.pth` file into the current Python environment so vanilla `adk web` imports `truclaw_adk.autopatch` at interpreter startup. The autopatch wraps every future `google.adk.agents.LlmAgent` constructor and installs TruClaw's `before_tool_callback` on all agents.

## Commands
```bash
truclaw install
truclaw doctor
truclaw status
truclaw pair
```

## State
Default state is project-local:
```text
./.truclaw/security-ledger.jsonl
./.truclaw/memory.md
./.truclaw/devices/paired.json
```
Pairing shape is OpenClaw-compatible:
```json
{
  "b9ebe80e7977811c56dd2bd0e9960128": {
    "publicKey": "xxx",
    "apnsToken": "yyy",
    "fcmToken": "fff",
    "platform": "ios",
    "pairedAt": "2026-04-22T01:54:38.741Z"
  }
}
```
Override state root:
```bash
export TRUCLAW_STATE_DIR="./.truclaw"
```

## Logs
All important TruClaw logs are prefixed with:
```text
[OPENCLAW] TruClaw ...
```
Important checkpoints logged:
- install/autopatch activation
- LlmAgent construction and guardrail attachment
- pair start, relay polling, pairing saved
- pre-tool guardrail invocation
- safe-tool bypass
- Anthropic classifier decision/errors
- challenge send/poll
- JWT verification
- allow/block outcome
- ledger append

## Test flow
1. Install:
```bash
pip install -e .
truclaw install
truclaw doctor
```
2. Start ADK:
```bash
adk web
```
3. Pair Phone in ADK

Before issuing challenges, you must pair your mobile device with your local TruClaw instance.

**A. Pre-requisites**
1. Install the TruClaw iOS app: [https://apps.apple.com/us/app/truclaw/id6749509039]()
2. Open the app and grant permissions for **Notifications** and **Camera** use.

**B. Initiation**

Run the pairing command via the ADK UI:
```text
pair my TruClaw phone
```
Or via the terminal:
```bash
truclaw pair
```
The terminal will output the session details and a pairing link:
```json
[OPENCLAW] TruClaw [pair] started sessionId=11ca8cd1d89f4b592c754550485a74e4
{
  "status": "pairing_started",
  "sessionId": "11ca8cd1d89f4b592c754550485a74e4",
  "pairingLink": "https://aasa.trusources.ai/openclaw?sessionId=11ca8cd1d89f4b592c754550485a74e4&webhookURL=https%3A//trukyc-relay.trusources.workers.dev/pair/11ca8cd1d89f4b592c754550485a74e4",
  "qrImageUrl": "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=https%3A//aasa.trusources.ai/openclaw%3FsessionId%3D11ca8cd1d89f4b592c754550485a74e4%26webhookURL%3Dhttps%253A//trukyc-relay.trusources.workers.dev/pair/11ca8cd1d89f4b592c754550485a74e4"
}
[OPENCLAW] TruClaw [pair] waiting for mobile client...
```

**C. Completion**

Complete the link using one of two methods:
* **Direct Link:** Open the `pairingLink` URL directly on the iPhone where TruClaw is installed. It will automatically redirect and open the app to finish pairing.
* **QR Scan:** Open the `qrImageUrl` on your MacBook and scan it using the TruClaw app on your iPhone.

Once finished, the pairing state is saved locally in your ADK home directory at `./.truclaw/devices/paired.json`. You are now ready to authorize agentic challenges!

4. Confirm pairing persisted:
```bash
cat ./.truclaw/devices/paired.json
truclaw status
```
5. Safe action should pass without phone approval:
```text
show my positions
```
6. Dangerous action should trigger phone approval before tool execution:
```text
buy NVDA at 100
```
Expected logs include:
```text
[OPENCLAW] TruClaw [guardrail] pre-tool ...
[OPENCLAW] TruClaw [guardrail] dangerous action requires phone approval ...
[OPENCLAW] TruClaw [challenge] sending push ...
[OPENCLAW] TruClaw [challenge] approved ...
[OPENCLAW] TruClaw [guardrail] approved; allowing tool=...
```
If approval is denied/expired/invalid, the tool is skipped and ADK receives:
```json
{"status":"blocked","blocked_by":"TruClaw", ...}
```
