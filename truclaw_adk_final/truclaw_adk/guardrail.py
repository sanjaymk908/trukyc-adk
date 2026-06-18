from typing import Any, Dict
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


def _user_id(tool_context: Any) -> str:
    for attr in ("_invocation_context", "invocation_context"):
        v = getattr(tool_context, attr, None)
        if v is not None and hasattr(v, "user_id"):
            try:
                return v.user_id
            except Exception:
                pass
    return "default"


def _root_agent_id(tool_context: Any) -> str:
    """
    Derive agentId from the root agent's name in the invocation context.
    Falls back to the immediate agent name, then 'unknown'.
    """
    for attr in ("_invocation_context", "invocation_context"):
        v = getattr(tool_context, attr, None)
        if v is None:
            continue
        # ADK stores the root agent on the invocation context
        root = getattr(v, "root_agent", None) or getattr(v, "agent", None)
        if root is not None:
            name = getattr(root, "name", None)
            if name:
                return name
    return _agent_name(tool_context)


def _ensure_policy_and_usage_loaded(agent_id: str) -> None:
    """
    Warm up policy and usage caches for this agent on first call.
    Both loads are no-ops if already cached.
    """
    from .policy import load_policy, load_usage_summary
    load_policy(agent_id)
    load_usage_summary(agent_id)


async def truclaw_before_tool_callback(
    tool: Any = None,
    args: Any = None,
    tool_context: Any = None,
    **kwargs,
) -> Dict[str, Any] | None:
    tool = tool or kwargs.get("tool")
    args = args if args is not None else kwargs.get("args") or kwargs.get("tool_args") or {}
    tool_context = tool_context or kwargs.get("tool_context")

    tool_name = _tool_name(tool)
    agent_name = _agent_name(tool_context)
    agent_id = _root_agent_id(tool_context)
    user_id = _user_id(tool_context)

    log(f"[guardrail] pre-tool agent={agent_name} agentId={agent_id} tool={tool_name} userId={user_id}")

    # Ensure policy and usage summary are loaded (cached after first call)
    _ensure_policy_and_usage_loaded(agent_id)

    decision = await check_danger(tool_name, args, agent_id=agent_id, user_id=user_id)

    base_event = {
        "agentName": agent_name,
        "agentId": agent_id,
        "toolName": tool_name,
        "toolArgs": args,
        "userId": user_id,
        "dangerous": decision.get("dangerous"),
        "reason": decision.get("reason"),
        "actionTitle": decision.get("actionTitle"),
        "actionBody": decision.get("actionBody"),
        "classifierRaw": decision.get("classifierRaw"),
        "scriptPath": decision.get("scriptPath"),
        "scriptSha256": decision.get("scriptSha256"),
        "scriptContentExcerpt": decision.get("scriptContent"),
        "safeBypass": decision.get("safeBypass", False),
        "thresholdViolation": decision.get("thresholdViolation", False),
    }

    if not decision.get("dangerous"):
        append_event({**base_event, "allowed": True, "approvalRequired": False})
        log(f"[guardrail] allow safe tool={tool_name}")
        return None

    if not config.ENFORCE:
        append_event({**base_event, "allowed": True, "approvalRequired": True, "enforce": False})
        log(f"[guardrail] dangerous but TRUCLAW_ENFORCE=0 allow tool={tool_name}")
        return None

    log(f"[guardrail] dangerous action requires phone approval tool={tool_name} reason={decision.get('reason')} userId={user_id}")

    approval = await send_challenge(
        decision.get("actionTitle") or f"Approve: {tool_name}",
        decision.get("actionBody") or "",
        decision.get("reason") or "dangerous action",
        tool_name,
        args,
        user_id=user_id,
    )

    if approval.get("approved"):
        append_event({**base_event, "allowed": True, "approvalRequired": True, "approval": approval})
        log(f"[guardrail] approved; allowing tool={tool_name} userId={user_id}")
        return None

    append_event({**base_event, "allowed": False, "approvalRequired": True, "approval": approval})
    log(f"[guardrail] blocked tool={tool_name} userId={user_id} reason={approval.get('reason')}")

    return {
        "status": "blocked",
        "blocked_by": "TruClaw",
        "tool": tool_name,
        "reason": approval.get("reason") or decision.get("reason"),
        "actionTitle": decision.get("actionTitle"),
        "actionBody": decision.get("actionBody"),
    }
