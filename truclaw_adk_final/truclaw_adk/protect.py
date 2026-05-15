from typing import Any, Callable
from .guardrail import truclaw_before_tool_callback
from .logging import log

_PATCHED_ATTR = "_truclaw_adk_protected"


def compose_callbacks(existing: Any) -> Callable:
    async def cb(tool=None, args=None, tool_context=None, **kwargs):
        blocked = await truclaw_before_tool_callback(
            tool=tool,
            args=args,
            tool_context=tool_context,
            **kwargs,
        )
        if blocked is not None:
            return blocked
        if existing is None:
            return None
        result = existing(
            tool=tool,
            args=args,
            tool_context=tool_context,
            **kwargs,
        )
        if hasattr(result, "__await__"):
            result = await result
        return result

    cb._truclaw_wrapped = True
    return cb


def _agent_tools(agent: Any):
    return getattr(agent, "tools", None) or []


def _agent_sub_agents(agent: Any):
    return getattr(agent, "sub_agents", None) or []


def _make_pair_tool(user_id: str) -> Any:
    """Build a truclaw_pair FunctionTool for this user_id."""
    from google.adk.tools import FunctionTool

    async def truclaw_pair() -> dict:
        """Pair a TruClaw mobile device for biometric authorization. Call this when the user asks to pair their phone or TruClaw device."""
        from .pairing import start_pairing
        result = await start_pairing(user_id=user_id, start_background_poll=True)
        if result.get("status") == "error":
            return {"error": result.get("reason")}
        return {
            "message": f"Open this link on your iPhone to pair with TruClaw:\n{result['pairingLink']}\n\nOr scan the QR code at:\n{result['qrImageUrl']}",
            "pairingLink": result["pairingLink"],
            "qrImageUrl": result["qrImageUrl"],
            "sessionId": result["sessionId"],
            "userId": user_id,
        }

    truclaw_pair.__name__ = "truclaw_pair"
    truclaw_pair.__doc__ = "Pair a TruClaw mobile device for biometric authorization. Call this when the user asks to pair their phone or TruClaw device."
    return FunctionTool(truclaw_pair)


def _get_user_id_from_context(agent: Any) -> str:
    """Best-effort extract userId from agent context at protect time."""
    return "default"


def _inject_pair_tool(agent: Any, user_id: str) -> None:
    """Inject truclaw_pair tool into agent if not already present."""
    tools = _agent_tools(agent)
    existing_names = [
        getattr(t, "name", None) or getattr(t, "__name__", None)
        for t in tools
    ]
    if "truclaw_pair" not in existing_names:
        try:
            pair_tool = _make_pair_tool(user_id)
            tools.append(pair_tool)
            log(f"[protect] injected truclaw_pair tool agent={getattr(agent, 'name', 'unknown')}")
        except Exception as e:
            log(f"[protect] could not inject truclaw_pair tool: {e}")


def protect_agent_tree(agent: Any, user_id: str = "default") -> Any:
    """
    Protect only the discovered user root_agent tree.
    This intentionally does NOT patch LlmAgent globally and does NOT touch
    ADK/MCP internals.
    """
    seen = set()

    def walk(a: Any):
        if id(a) in seen:
            return
        seen.add(id(a))
        name = getattr(a, "name", "unknown")
        tools = _agent_tools(a)

        if tools:
            existing = getattr(a, "before_tool_callback", None)
            if getattr(existing, "_truclaw_wrapped", False):
                log(f"[protect] already protected agent={name} tools={len(tools)}")
            else:
                try:
                    setattr(a, "before_tool_callback", compose_callbacks(existing))
                    setattr(a, _PATCHED_ATTR, True)
                    log(f"[protect] attached guardrail agent={name} tools={len(tools)}")
                except Exception as e:
                    raise RuntimeError(
                        f"TruClaw could not protect agent {name}: {e}"
                    )
            _inject_pair_tool(a, user_id)

        for child in _agent_sub_agents(a):
            walk(child)

    walk(agent)
    assert_agent_tree_protected(agent)
    return agent


def assert_agent_tree_protected(agent: Any) -> None:
    failures = []
    seen = set()

    def walk(a: Any):
        if id(a) in seen:
            return
        seen.add(id(a))
        name = getattr(a, "name", "unknown")
        tools = _agent_tools(a)
        if tools:
            cb = getattr(a, "before_tool_callback", None)
            if not getattr(cb, "_truclaw_wrapped", False):
                failures.append(name)
        for child in _agent_sub_agents(a):
            walk(child)

    walk(agent)
    if failures:
        raise RuntimeError(
            "Unprotected tool-bearing ADK agents: " + ", join(failures)"
        )
    log("[protect] agent tree verified protected")
