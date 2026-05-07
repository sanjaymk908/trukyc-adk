import json, time, hashlib
from pathlib import Path
from typing import Any, Dict, List
from . import config
from .logging import log

LEDGER_PATH = config.STATE_DIR / "security-ledger.jsonl"
MEMORY_PATH = config.STATE_DIR / "memory.md"


def _jsonable(x: Any) -> Any:
    try:
        json.dumps(x)
        return x
    except Exception:
        return repr(x)


def append_event(event: Dict[str, Any]) -> str:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    event = dict(event)
    event.setdefault("ts", time.time())
    event.setdefault("id", hashlib.sha256(json.dumps(event, sort_keys=True, default=str).encode()).hexdigest()[:16])
    event = _jsonable(event)
    with LEDGER_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, sort_keys=True, default=str) + "\n")
    _append_memory(event)
    log(f"[ledger] appended id={event['id']} tool={event.get('toolName')} allowed={event.get('allowed')} dangerous={event.get('dangerous')}")
    return event["id"]


def read_events(limit: int = 100) -> List[Dict[str, Any]]:
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


def prior_summary(limit: int = 30) -> str:
    events = read_events(limit)
    if not events:
        return "No prior actions."
    lines = []
    for i, e in enumerate(events, 1):
        args = json.dumps(e.get("toolArgs"), default=str)[:1200]
        reason = e.get("reason") or e.get("risk", {}).get("reason") or "n/a"
        lines.append(f"{i}. {e.get('toolName')}({args}) — {reason} — allowed={e.get('allowed')}")
    return "\n".join(lines)


def dangerous_prior_flag(limit: int = 5) -> str:
    dangerous = [e for e in read_events(100) if e.get("dangerous")]
    if not dangerous:
        return ""
    lines = []
    for e in dangerous[-limit:]:
        lines.append(f"- {e.get('toolName')}({json.dumps(e.get('toolArgs'), default=str)[:800]}) — {e.get('reason')}")
    return "\n\nIMPORTANT — prior dangerous actions:\n" + "\n".join(lines)


def _append_memory(e: Dict[str, Any]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = f"- {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(e.get('ts', time.time())))} {e.get('toolName')} dangerous={e.get('dangerous')} allowed={e.get('allowed')} reason={e.get('reason')}\n"
    with MEMORY_PATH.open("a", encoding="utf-8") as f:
        f.write(line)
