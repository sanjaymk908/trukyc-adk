import json
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List
from . import config
from .logging import log

LEDGER_PATH = config.STATE_DIR / "security-ledger.jsonl"
MEMORY_PATH = config.STATE_DIR / "memory.md"

GCS_LEDGER_BLOB = "truclaw/security-ledger.jsonl"

_ledger_loaded = False

# Per-agent memory cache: agent_id -> markdown text (empty string = no memory yet)
_memory_cache: Dict[str, str] = {}


def _gcs_memory_blob(agent_id: str) -> str:
    return f"truclaw/policies/{agent_id}/memory.md"


def _memory_local(agent_id: str) -> Path:
    return config.STATE_DIR / "policies" / agent_id / "memory.md"


def _ensure_ledger_loaded() -> None:
    global _ledger_loaded
    if _ledger_loaded:
        return
    from .gcs_storage import gcs_download
    gcs_download(LEDGER_PATH, GCS_LEDGER_BLOB)
    _ledger_loaded = True


def _load_memory(agent_id: str) -> str:
    """Load cron-generated behavioral memory for this agent. Cached in-process."""
    if agent_id in _memory_cache:
        return _memory_cache[agent_id]
    local = _memory_local(agent_id)
    if not local.exists():
        from .gcs_storage import gcs_download
        gcs_download(local, _gcs_memory_blob(agent_id))
    if local.exists():
        try:
            text = local.read_text(encoding="utf-8")
            _memory_cache[agent_id] = text
            return text
        except Exception:
            pass
    _memory_cache[agent_id] = ""
    return ""


def _jsonable(x: Any) -> Any:
    try:
        json.dumps(x)
        return x
    except Exception:
        return repr(x)


def append_event(event: Dict[str, Any]) -> str:
    _ensure_ledger_loaded()
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    event = dict(event)
    event.setdefault("ts", time.time())
    event.setdefault(
        "id",
        hashlib.sha256(
            json.dumps(event, sort_keys=True, default=str).encode()
        ).hexdigest()[:16],
    )
    event = _jsonable(event)
    with LEDGER_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True, default=str) + "\n")
    from .gcs_storage import gcs_upload
    gcs_upload(LEDGER_PATH, GCS_LEDGER_BLOB)
    log(
        f"[ledger] appended id={event['id']} tool={event.get('toolName')} "
        f"allowed={event.get('allowed')} dangerous={event.get('dangerous')}"
    )
    return event["id"]


def read_events(limit: int = 100) -> List[Dict[str, Any]]:
    _ensure_ledger_loaded()
    if not LEDGER_PATH.exists():
        return []
    lines = LEDGER_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def prior_summary(limit: int = 30, agent_id: str = "") -> str:
    """
    Returns classifier context: cross-session behavioral memory (from cron)
    followed by current-session recent events.
    """
    parts: List[str] = []

    # Cross-session memory written by cron aggregator
    if agent_id:
        memory = _load_memory(agent_id)
        if memory:
            parts.append("=== Cross-session behavioral memory ===")
            parts.append(memory.strip())
            parts.append("")

    # Current-session recent events
    events = read_events(limit)
    if events:
        parts.append("=== Current session actions ===")
        for i, e in enumerate(events, 1):
            args = json.dumps(e.get("toolArgs"), default=str)[:1200]
            reason = e.get("reason") or e.get("risk", {}).get("reason") or "n/a"
            parts.append(
                f"{i}. {e.get('toolName')}({args}) — {reason} — allowed={e.get('allowed')}"
            )

    return "\n".join(parts) if parts else "No prior actions."


def dangerous_prior_flag(limit: int = 5) -> str:
    dangerous = [e for e in read_events(100) if e.get("dangerous")]
    if not dangerous:
        return ""
    lines = []
    for e in dangerous[-limit:]:
        lines.append(
            f"- {e.get('toolName')}({json.dumps(e.get('toolArgs'), default=str)[:800]}) "
            f"— {e.get('reason')}"
        )
    return "\n\nIMPORTANT — prior dangerous actions:\n" + "\n".join(lines)


def clear_ledger() -> None:
    """Admin: clear local ledger and GCS blob."""
    if LEDGER_PATH.exists():
        LEDGER_PATH.unlink()
    from .gcs_storage import gcs_delete
    gcs_delete(GCS_LEDGER_BLOB)
    global _ledger_loaded
    _ledger_loaded = False
    log("[ledger] ledger cleared")


def clear_memory(agent_id: str = "") -> None:
    """Admin: clear local memory cache. GCS copy is managed by the cron job."""
    _memory_cache.pop(agent_id, None)
    if agent_id:
        local = _memory_local(agent_id)
        if local.exists():
            local.unlink()
    elif MEMORY_PATH.exists():
        MEMORY_PATH.unlink()
    log(f"[ledger] memory cache cleared agentId={agent_id or 'all'}")


def clear_all() -> None:
    """Admin: clear both ledger and memory."""
    clear_ledger()
    clear_memory()
    log("[ledger] all state cleared")
