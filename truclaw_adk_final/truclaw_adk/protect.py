from typing import Any, Callable
from .guardrail import truclaw_before_tool_callback
from .logging import log

_PATCHED_ATTR = "_truclaw_adk_protected"


def compose_callbacks(existing: Any) -> Callable:
    async def cb(tool=None, args=None, tool_context=None, **kwargs):
        blocked = await truclaw_before_tool_callback(tool=tool, args=args, tool_context=tool_context, **kwargs)
        if blocked is not None:
            return blocked
        if existing is None:
            return None
        result = existing(tool=tool, args=args, tool_context=tool_context, **kwargs)
        if hasattr(result, "__await__"):
            result = await result
        return result
    cb._truclaw_wrapped = True
    return cb


def protect_agent_tree(agent: Any) -> Any:
    seen = set()
    def walk(a: Any):
        if id(a) in seen:
            return
        seen.add(id(a))
        tools = getattr(a, "tools", None) or []
        if tools:
            existing = getattr(a, "before_tool_callback", None)
            if not getattr(existing, "_truclaw_wrapped", False):
                try:
                    setattr(a, "before_tool_callback", compose_callbacks(existing))
                    setattr(a, _PATCHED_ATTR, True)
                    log(f"[protect] attached guardrail agent={getattr(a, 'name', 'unknown')} tools={len(tools)}")
                except Exception as e:
                    raise RuntimeError(f"TruClaw could not protect agent {getattr(a, 'name', a)}: {e}")
        for child in getattr(a, "sub_agents", None) or []:
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
        tools = getattr(a, "tools", None) or []
        if tools and not getattr(getattr(a, "before_tool_callback", None), "_truclaw_wrapped", False):
            failures.append(getattr(a, "name", repr(a)))
        for child in getattr(a, "sub_agents", None) or []:
            walk(child)
    walk(agent)
    if failures:
        raise RuntimeError("Unprotected tool-bearing ADK agents: " + ", ".join(failures))
    log("[protect] agent tree verified protected")
