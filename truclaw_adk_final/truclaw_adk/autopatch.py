import os
from .logging import log
from .protect import compose_callbacks

_PATCHED = False


def install_autopatch() -> None:
    global _PATCHED
    if _PATCHED:
        return
    try:
        from google.adk.agents import LlmAgent
    except Exception as e:
        log(f"[autopatch] google.adk not importable yet: {e}")
        return
    orig_init = LlmAgent.__init__
    if getattr(orig_init, "_truclaw_patched", False):
        _PATCHED = True
        return

    def patched_init(self, *args, **kwargs):
        existing = kwargs.get("before_tool_callback")
        kwargs["before_tool_callback"] = compose_callbacks(existing)
        orig_init(self, *args, **kwargs)
        tools = getattr(self, "tools", None) or []
        if tools:
            log(f"[autopatch] guarded LlmAgent name={getattr(self, 'name', 'unknown')} tools={len(tools)}")
        else:
            log(f"[autopatch] guarded LlmAgent name={getattr(self, 'name', 'unknown')} tools=0")

    patched_init._truclaw_patched = True
    LlmAgent.__init__ = patched_init
    _PATCHED = True
    log("[autopatch] LlmAgent constructor patched; all future agents receive TruClaw guardrail")

install_autopatch()
