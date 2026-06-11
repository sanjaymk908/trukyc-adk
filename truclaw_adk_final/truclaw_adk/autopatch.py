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
    _patch_mcp_stdio_timeout()


def _patch_mcp_stdio_timeout() -> None:
    try:
        from google.adk.tools.mcp_tool import session_context as sc
        original_run = sc.SessionContext._run

        async def patched_run(self):
            original_set = self._ready_event.set

            def patched_set():
                if self._session is not None:
                    from datetime import timedelta
                    timeout = timedelta(seconds=120)
                    try:
                        self._session._read_timeout_seconds = timeout
                    except Exception:
                        pass
                    try:
                        self._session._session_read_timeout_seconds = timeout
                    except Exception:
                        pass
                original_set()

            self._ready_event.set = patched_set
            await original_run(self)

        sc.SessionContext._run = patched_run
        log("[autopatch] patched MCP stdio read timeout to 120s")
    except Exception as e:
        log(f"[autopatch] could not patch MCP stdio timeout: {e}")


def _register_on_app(app) -> None:
    """Register Truclaw routes on a FastAPI app instance."""
    if not getattr(app.state, "_truclaw_pair_route_registered", False):
        from .pair_route import register_pair_route
        register_pair_route(app)
        app.state._truclaw_pair_route_registered = True
        log("[autopatch] /pair route registered")
    if not getattr(app.state, "_truclaw_chat_registered", False):
        try:
            from .chat_handler import register_chat_handler
            register_chat_handler(app)
            app.state._truclaw_chat_registered = True
            log("[autopatch] /chat route registered")
        except Exception as e:
            log(f"[autopatch] /chat route skipped: {e}")


def _find_running_fastapi_app():
    """Find an already-created FastAPI app via the garbage collector."""
    try:
        import gc
        from fastapi import FastAPI
        candidates = [obj for obj in gc.get_objects() if type(obj) is FastAPI]
        if candidates:
            # Prefer the app with the most routes (the main server app)
            return max(candidates, key=lambda a: len(a.routes))
    except Exception as e:
        log(f"[autopatch] gc app search failed: {e}")
    return None


def _try_register_pair_route() -> None:
    try:
        from google.adk.cli.adk_web_server import AdkWebServer

        # --- Try to register on an already-running app first ---
        existing_app = _find_running_fastapi_app()
        if existing_app is not None:
            log("[autopatch] found existing FastAPI app via gc — registering routes immediately")
            _register_on_app(existing_app)
        else:
            log("[autopatch] no existing FastAPI app found via gc")

        # --- Also patch get_fast_api_app for future calls ---
        original = AdkWebServer.get_fast_api_app

        if getattr(original, "_truclaw_pair_route_patched", False):
            log("[autopatch] /pair route patch already installed")
            return

        def _patched_get_fast_api_app(self, *args, **kwargs):
            app = original(self, *args, **kwargs)
            _register_on_app(app)
            return app

        _patched_get_fast_api_app._truclaw_pair_route_patched = True
        AdkWebServer.get_fast_api_app = _patched_get_fast_api_app
        log("[autopatch] AdkWebServer.get_fast_api_app patched for /pair route")
    except Exception as e:
        log(f"[autopatch] could not patch AdkWebServer.get_fast_api_app: {e}")


install_autopatch()
