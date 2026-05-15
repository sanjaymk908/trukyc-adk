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
            # extract user_id from invocation context if available
            user_id = "default"
            try:
                ctx = args[0] if args else kwargs.get("invocation_context")
                if ctx is not None and hasattr(ctx, "user_id"):
                    user_id = ctx.user_id
            except Exception:
                pass

            log(f"[autopatch] protecting active agent tree root={name} userId={user_id}")
            protect_agent_tree(self, user_id=user_id)
            _PROTECTED_IDS.add(agent_id)
            log(f"[autopatch] active agent tree protected root={name} userId={user_id}")

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
        from google.adk.cli.adk_web_server import AdkWebServer

        original = AdkWebServer.get_fast_api_app

        if getattr(original, "_truclaw_pair_route_patched", False):
            log("[autopatch] /pair route patch already installed")
            return

        def _patched_get_fast_api_app(self, *args, **kwargs):
            app = original(self, *args, **kwargs)
            if not getattr(app.state, "_truclaw_pair_route_registered", False):
                from .pair_route import register_pair_route
                register_pair_route(app)
                app.state._truclaw_pair_route_registered = True
                log("[autopatch] /pair route registered")
            return app

        _patched_get_fast_api_app._truclaw_pair_route_patched = True
        AdkWebServer.get_fast_api_app = _patched_get_fast_api_app
        log("[autopatch] AdkWebServer.get_fast_api_app patched for /pair route")
    except Exception as e:
        log(f"[autopatch] could not patch AdkWebServer.get_fast_api_app: {e}")


install_autopatch()
