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
    from google.adk.tools import FunctionTool

    async def truclaw_pair() -> dict:
        """Pair a TruClaw mobile device for biometric authorization. Call this when the user asks to pair their phone or TruClaw device."""
        from .pairing import start_pairing
        result = await start_pairing(user_id=user_id, start_background_poll=True)
        if result.get("status") == "error":
            return {"error": result.get("reason")}
        return {
            "message": (
                f"Open this link on your iPhone to pair with TruClaw:\n"
                f"{result['pairingLink']}\n\n"
                f"Or scan the QR code at:\n"
                f"{result['qrImageUrl']}"
            ),
            "pairingLink": result["pairingLink"],
            "qrImageUrl": result["qrImageUrl"],
            "sessionId": result["sessionId"],
            "userId": user_id,
        }

    truclaw_pair.__name__ = "truclaw_pair"
    truclaw_pair.__doc__ = (
        "Pair a TruClaw mobile device for biometric authorization. "
        "Call this when the user asks to pair their phone or TruClaw device."
    )
    return FunctionTool(truclaw_pair)


def _make_status_tool(user_id: str) -> Any:
    from google.adk.tools import FunctionTool

    async def truclaw_status() -> dict:
        """Check TruClaw pairing status for the current user. Call this when the user asks about their TruClaw pairing status or if their device is paired."""
        from .pairing import find_paired_devices_for_user
        devices = find_paired_devices_for_user(user_id)
        if not devices:
            return {
                "paired": False,
                "userId": user_id,
                "message": (
                    f"No device paired for userId={user_id}. "
                    f"Ask me to pair your TruClaw device."
                ),
            }
        return {
            "paired": True,
            "deviceCount": len(devices),
            "userId": user_id,
            "devices": [
                {
                    "platform": d.get("platform", "unknown"),
                    "pairedAt": d.get("pairedAt", "unknown"),
                }
                for d in devices
            ],
            "message": f"{len(devices)} device(s) paired for userId={user_id}.",
        }

    truclaw_status.__name__ = "truclaw_status"
    truclaw_status.__doc__ = (
        "Check TruClaw pairing status for the current user. "
        "Call this when the user asks about their TruClaw pairing status "
        "or if their device is paired."
    )
    return FunctionTool(truclaw_status)


def _inject_truclaw_tools(agent: Any, user_id: str) -> None:
    tools = _agent_tools(agent)
    existing_names = [
        getattr(t, "name", None) or getattr(t, "__name__", None)
        for t in tools
    ]
    name = getattr(agent, "name", "unknown")

    if "truclaw_pair" not in existing_names:
        try:
            tools.append(_make_pair_tool(user_id))
            log(f"[protect] injected truclaw_pair agent={name}")
        except Exception as e:
            log(f"[protect] could not inject truclaw_pair: {e}")

    if "truclaw_status" not in existing_names:
        try:
            tools.append(_make_status_tool(user_id))
            log(f"[protect] injected truclaw_status agent={name}")
        except Exception as e:
            log(f"[protect] could not inject truclaw_status: {e}")


def protect_agent_tree(agent: Any, user_id: str = "default") -> Any:
    """
    Protect only the discovered user root_agent tree.
    This intentionally does NOT patch LlmAgent globally and does NOT touch
    ADK/MCP internals.
    TruClaw meta-tools (truclaw_pair, truclaw_status) are injected on the
    root agent only to prevent orchestrator delegation loops.
    """
    seen = set()

    def walk(a: Any, is_root: bool = False):
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

            if is_root:
                _inject_truclaw_tools(a, user_id)

        for child in _agent_sub_agents(a):
            walk(child, is_root=False)

    walk(agent, is_root=True)
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
            "Unprotected tool-bearing ADK agents: " + ", ".join(failures)
        )
    log("[protect] agent tree verified protected")
