# TruClaw ADK Guardrail

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
truclaw doctor
truclaw status
truclaw pair
truclaw uninstall
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

3. Pair phone in ADK UI:

```text
pair my TruClaw phone
```

or terminal:

```bash
truclaw pair
```

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
