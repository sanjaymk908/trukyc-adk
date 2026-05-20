import json
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from . import config
from .ledger import prior_summary, dangerous_prior_flag
from .logging import log


SAFE_TOOLS = {
    "read",
    "session_status",
    "list",
    "ls",
    "web_search",
    "web_fetch",
    "browser_snapshot",
    "status",
    "truclaw_pair",
    "truclaw_status",
    "transfer_to_agent",
    "transfer_to_agent_tool",
    "agent_transfer",
    "load_artifacts",
    "list_artifacts",
    "save_artifacts",
}

SCRIPT_EXECUTION_PATTERN = re.compile(
    r"^(python3?|bash|sh|node|ruby|perl|php|pwsh|powershell)\s+\S"
)

SCRIPT_PATH_PATTERN = re.compile(
    r"^(?:python3?|bash|sh|node|ruby|perl|php|pwsh|powershell)\s+"
    r"([\w./~-]+\.(?:py|sh|js|ts|rb|pl|php|ps1))"
)

FINANCIAL_FUNCTION_PATTERN = re.compile(
    r"\b("
    r"place_order|submit_order|execute_trade|cancel_order|sell_order|buy_order|"
    r"transfer|send_payment|wire_transfer|withdraw|deposit|execute_transaction|"
    r"approve_claim|modify_policy"
    r")\s*\(",
    re.I,
)

ALWAYS_DANGEROUS_TOOLS = {
    "place_trade",
    "execute_trade",
    "send_email",
    "send_email_via_porteden",
    "delete_email",
    "forward_email",
    "reply_email",
}


def command_from_args(tool_args: Any) -> str:
    if isinstance(tool_args, dict):
        return str(
            tool_args.get("command")
            or tool_args.get("cmd")
            or json.dumps(tool_args, default=str)
        )
    return str(tool_args)


def resolve_script_content(command: str) -> Dict[str, Any]:
    m = SCRIPT_PATH_PATTERN.match(command)
    if not m:
        return {"scriptContent": None}
    p = Path(m.group(1)).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        truncated = len(content) > 6000
        excerpt = content[:6000] + ("\n...[truncated]" if truncated else "")
        return {
            "scriptPath": str(p),
            "scriptSha256": hashlib.sha256(content.encode()).hexdigest(),
            "scriptContent": excerpt,
            "scriptTruncated": truncated,
        }
    except Exception as e:
        return {
            "scriptPath": str(p),
            "scriptReadError": str(e),
            "scriptContent": None,
        }


def extract_json_object(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty classifier response")
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
        raise ValueError("classifier JSON was not an object")
    except Exception:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    if fenced:
        obj = json.loads(fenced.group(1))
        if isinstance(obj, dict):
            return obj
        raise ValueError("classifier fenced JSON was not an object")
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        obj = json.loads(text[start: end + 1])
        if isinstance(obj, dict):
            return obj
        raise ValueError("classifier embedded JSON was not an object")
    raise ValueError(f"No JSON object found in classifier response: {text[:300]}")


def normalize_classifier_decision(decision: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    dangerous = bool(decision.get("dangerous"))
    reason = str(decision.get("reason") or decision.get("rationale") or "classified")
    action = str(decision.get("action") or decision.get("actionDescription") or f"Execute {tool_name}")
    return {
        "dangerous": dangerous,
        "reason": reason,
        "action": action,
        "classifierRaw": decision,
    }


async def _gemini_generate(system: str, user: str, max_tokens: int = 300) -> str:
    """Call Gemini API for classification."""
    from google import genai
    from google.genai import types as genai_types

    client = genai.Client(api_key=config.GOOGLE_API_KEY)
    response = await client.aio.models.generate_content(
        model=config.GEMINI_CLASSIFIER_MODEL,
        contents=user,
        config=genai_types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text.strip()


async def get_action_description(
    tool_name: str,
    tool_args: Any,
    script_content: Optional[str],
) -> str:
    if not config.GOOGLE_API_KEY:
        return f"Execute: {tool_name}"

    prompt = (
        f"Script content:\n```\n{script_content}\n```"
        if script_content
        else f"Tool: {tool_name}\nArgs: {json.dumps(tool_args, default=str)}"
    )
    prompt += dangerous_prior_flag()
    prompt += (
        "\n\nWrite one sentence under 90 chars describing what this action DOES. "
        "Start with a verb."
    )

    try:
        text = await _gemini_generate("You are a security analyst.", prompt, max_tokens=60)
        return text[:87] + "..." if len(text) > 90 else text
    except Exception:
        return f"Execute: {tool_name}"


async def check_danger(tool_name: str, tool_args: Any) -> Dict[str, Any]:
    log(f"[guardrail] danger check tool={tool_name}")

    normalized = tool_name.split(".")[-1]

    if normalized in SAFE_TOOLS or tool_name in SAFE_TOOLS:
        log(f"[guardrail] safe-tool bypass tool={tool_name}")
        return {
            "dangerous": False,
            "reason": "safe tool bypass",
            "action": f"Run {tool_name}",
            "safeBypass": True,
        }

    command = command_from_args(tool_args)
    script = resolve_script_content(command)

    if normalized in ALWAYS_DANGEROUS_TOOLS or tool_name in ALWAYS_DANGEROUS_TOOLS:
        action = await get_action_description(tool_name, tool_args, script.get("scriptContent"))
        return {"dangerous": True, "reason": "always-dangerous tool", "action": action, **script}

    if SCRIPT_EXECUTION_PATTERN.match(command):
        action = await get_action_description(tool_name, tool_args, script.get("scriptContent"))
        return {"dangerous": True, "reason": "script/interpreter execution is always dangerous", "action": action, **script}

    if FINANCIAL_FUNCTION_PATTERN.search(command):
        action = await get_action_description(tool_name, tool_args, script.get("scriptContent"))
        return {"dangerous": True, "reason": "financial/business action pattern", "action": action, **script}

    if not config.GOOGLE_API_KEY:
        log("[guardrail] GOOGLE_API_KEY missing; fail closed")
        return {"dangerous": True, "reason": "GOOGLE_API_KEY not configured", "action": f"Execute {tool_name}", **script}

    system = """
You are a security guardrail for an AI agent. Your job is to decide if a tool call
should be blocked and require human biometric approval before execution.

Reply with JSON only. No markdown. No prose.

Schema:
{
  "dangerous": boolean,
  "reason": "one line",
  "action": "under 90 chars, starts with a verb"
}

Core principle:
A tool call is dangerous if it causes an irreversible or harmful side effect in the
real world, or if it is part of a cumulative pattern that would cause such harm.

Ask yourself three questions:

1. DIRECT HARM: Does this single tool call, by itself, cause an irreversible or
   harmful change in the world? Examples: sending money, deleting data, sending a
   message, executing a trade, modifying permissions, installing code, exfiltrating
   data. If yes → dangerous.

2. CUMULATIVE HARM: Does this tool call, considered alongside prior actions in this
   session, form part of a suspicious pattern that a human would want to review?
   Examples: repeated transactions below detection limits, escalating amounts,
   bulk reads followed by external sends, probing behavior with modified args,
   reading credentials then making network calls. If yes → dangerous.

3. STRUCTURAL ACTION: Is this tool call purely structural — routing, delegation,
   reading data for display, searching, listing, querying — with no real-world side
   effect of its own, and no suspicious cumulative pattern? If yes → safe.

Key distinctions:
- Reading data is safe. Sending data externally is dangerous.
- Agent transfers are structural and always safe.
- A single read of sensitive data is safe. A read immediately followed by an
  external send is dangerous (cumulative).
- Legitimate multi-step agentic workflows (transfer → read → act) are normal.
  The act step should be flagged, not the transfer or read steps.
- One small transaction may be fine. Ten identical small transactions in one
  session is suspicious regardless of individual size.

When in doubt, prefer dangerous. It is better to require a human to approve a
legitimate action than to allow a harmful action without oversight.
""".strip()

    user = (
        f"Tool: {tool_name}\n"
        f"Args: {json.dumps(tool_args, default=str)}\n"
        f"Prior actions:\n{prior_summary()}\n"
        f"{dangerous_prior_flag()}\n"
    )

    if script.get("scriptContent"):
        user += f"Script content:\n```\n{script['scriptContent']}\n```\n"

    try:
        text = await _gemini_generate(system, user, max_tokens=300)
        log(f"[guardrail] classifier raw={text[:300]}")
        decision = extract_json_object(text)
        normalized_decision = normalize_classifier_decision(decision, tool_name)
        log(
            f"[guardrail] classifier "
            f"dangerous={normalized_decision.get('dangerous')} "
            f"reason={normalized_decision.get('reason')}"
        )
        return {**normalized_decision, **script}
    except Exception as e:
        log(f"[guardrail] classifier error; fail closed error={e}")
        return {"dangerous": True, "reason": f"classifier error: {e}", "action": f"Execute {tool_name}", **script}
