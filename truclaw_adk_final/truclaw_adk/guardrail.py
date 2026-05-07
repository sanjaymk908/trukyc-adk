from typing import Any, Dict
import inspect
from .danger import check_danger
from .challenge import send_challenge
from .ledger import append_event, prior_summary
from . import config
from .logging import log


def _tool_name(tool: Any) -> str:
    return getattr(tool, "name", None) or getattr(tool, "__name__", None) or tool.__class__.__name__


def _agent_name(tool_context: Any) -> str:
    for attr in ("agent_name", "_invocation_context", "invocation_context"):
        v = getattr(tool_context, attr, None)
        if isinstance(v, str):
            return v
        if v is not None and hasattr(v, "agent"):
            return getattr(getattr(v, "agent"), "name", "unknown")
    return "unknown"


async def truclaw_before_tool_callback(tool: Any = None, args: Any = None, tool_context: Any = None, **kwargs) -> Dict[str, Any] | None:
    tool = tool or kwargs.get("tool")
    args = args if args is not None else kwargs.get("args") or kwargs.get("tool_args") or {}
    tool_context = tool_context or kwargs.get("tool_context")
    tool_name = _tool_name(tool)
    agent_name = _agent_name(tool_context)
    log(f"[guardrail] pre-tool agent={agent_name} tool={tool_name}")

    decision = await check_danger(tool_name, args)
    base_event = {
        "agentName": agent_name,
        "toolName": tool_name,
        "toolArgs": args,
        "priorSummary": prior_summary(),
        "dangerous": decision.get("dangerous"),
        "reason": decision.get("reason"),
        "action": decision.get("action"),
        "classifierRaw": decision.get("classifierRaw"),
        "scriptPath": decision.get("scriptPath"),
        "scriptSha256": decision.get("scriptSha256"),
        "scriptContentExcerpt": decision.get("scriptContent"),
        "safeBypass": decision.get("safeBypass", False),
    }

    if not decision.get("dangerous"):
        append_event({**base_event, "allowed": True, "approvalRequired": False})
        log(f"[guardrail] allow safe tool={tool_name}")
        return None

    if not config.ENFORCE:
        append_event({**base_event, "allowed": True, "approvalRequired": True, "enforce": False})
        log(f"[guardrail] dangerous but TRUCLAW_ENFORCE=0 allow tool={tool_name}")
        return None

    log(f"[guardrail] dangerous action requires phone approval tool={tool_name} reason={decision.get('reason')}")
    approval = await send_challenge(decision.get("action") or f"Execute {tool_name}", decision.get("reason") or "dangerous action", tool_name, args)
    if approval.get("approved"):
        append_event({**base_event, "allowed": True, "approvalRequired": True, "approval": approval})
        log(f"[guardrail] approved; allowing tool={tool_name}")
        return None

    append_event({**base_event, "allowed": False, "approvalRequired": True, "approval": approval})
    log(f"[guardrail] blocked tool={tool_name} reason={approval.get('reason')}")
    return {
        "status": "blocked",
        "blocked_by": "TruClaw",
        "tool": tool_name,
        "reason": approval.get("reason") or decision.get("reason"),
        "action": decision.get("action"),
    }
