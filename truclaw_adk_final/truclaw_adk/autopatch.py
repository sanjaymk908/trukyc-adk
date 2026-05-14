from .logging import log
from .protect import protect_agent_tree

_PATCHED = False
_PROTECTED_IDS = set()


def install_autopatch() -> None:
    global _PATCHED
    if _PATCHED:
        return

    from google.adk.agents.base_agent import BaseAgent

    original_run_async = BaseAgent.run_async

    if getattr(original_run_async, "_truclaw_wrapped", False):
        _PATCHED = True
        log("[autopatch] BaseAgent.run_async already patched")
        return

    async def patched_run_async(self, *args, **kwargs):
        agent_id = id(self)
        name = getattr(self, "name", "unknown")
        if agent_id not in _PROTECTED_IDS:
            log(f"[autopatch] protecting active agent tree root={name}")
            protect_agent_tree(self)
            _PROTECTED_IDS.add(agent_id)
            log(f"[autopatch] active agent tree protected root={name}")
        async for event in original_run_async(self, *args, **kwargs):
            yield event

    patched_run_async._truclaw_wrapped = True
    BaseAgent.run_async = patched_run_async
    _PATCHED = True
    log(
        "[autopatch] installed BaseAgent.run_async protector; "
        "no import hook, no constructor patch"
    )
    _try_register_pair_route()


def _try_register_pair_route() -> None:
    try:
        from google.adk.cli import fast_api as _fast_api_module

        _original_get_app = _fast_api_module.get_fast_api_app

        def _patched_get_app(*args, **kwargs):
            app = _original_get_app(*args, **kwargs)
            from .pair_route import register_pair_route
            register_pair_route(app)
            return app

        _fast_api_module.get_fast_api_app = _patched_get_app
        log("[autopatch] get_fast_api_app patched for /pair route")
    except Exception as e:
        log(f"[autopatch] could not patch get_fast_api_app: {e}")


install_autopatch()
