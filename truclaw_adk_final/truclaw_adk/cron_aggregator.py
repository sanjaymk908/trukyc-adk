"""
TruClaw usage aggregator — designed to run as a Google Cloud Run Job.

Reads security-ledger.jsonl from GCS for every agent that has a policy,
aggregates per-userId per-toolName daily and weekly counts,
writes usage_summary.json back to GCS for each agent.

Cloud Run Job entry point: python -m truclaw_adk.cron_aggregator

Environment variables required (same as the main service):
  TRUCLAW_GCS_BUCKET   — GCS bucket name
  TRUCLAW_STATE_DIR    — local scratch dir (default: ./.truclaw)

Schedule: deploy as a Cloud Run Job, trigger via Cloud Scheduler every hour.
  gcloud scheduler jobs create http truclaw-aggregator \
    --schedule="0 * * * *" \
    --uri="https://<CLOUD_RUN_JOB_TRIGGER_URL>" \
    --time-zone="UTC"
"""

import datetime
import json
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

GCS_BUCKET = os.getenv("TRUCLAW_GCS_BUCKET", "")
STATE_DIR = Path(os.getenv("TRUCLAW_STATE_DIR", "./.truclaw"))

LEDGER_BLOB_PATTERN = "truclaw/security-ledger.jsonl"   # single-agent default
POLICIES_PREFIX = "truclaw/policies/"                    # list prefix to find all agents


# --------------------------------------------------------------------------- #
# Logging (standalone — no dependency on truclaw_adk.logging)
# --------------------------------------------------------------------------- #

def _log(msg: str) -> None:
    ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"{ts} [cron_aggregator] {msg}", flush=True)


# --------------------------------------------------------------------------- #
# GCS helpers (standalone — avoids importing the full truclaw_adk package)
# --------------------------------------------------------------------------- #

def _gcs_client():
    from google.cloud import storage  # type: ignore
    return storage.Client()


def _list_agent_ids() -> List[str]:
    """
    Find all agentIds that have a policy in GCS by listing
    gs://<bucket>/truclaw/policies/<agentId>/TruClaw-Policies.json
    """
    if not GCS_BUCKET:
        return []
    try:
        client = _gcs_client()
        blobs = list(client.bucket(GCS_BUCKET).list_blobs(prefix=POLICIES_PREFIX))
        agent_ids = set()
        for blob in blobs:
            # truclaw/policies/<agentId>/TruClaw-Policies.json
            parts = blob.name[len(POLICIES_PREFIX):].split("/")
            if len(parts) >= 2 and parts[1] == "TruClaw-Policies.json":
                agent_ids.add(parts[0])
        return sorted(agent_ids)
    except Exception as e:
        _log(f"list agents error: {e}")
        return []


def _download_text(blob_name: str) -> str | None:
    if not GCS_BUCKET:
        return None
    try:
        client = _gcs_client()
        blob = client.bucket(GCS_BUCKET).blob(blob_name)
        if not blob.exists():
            return None
        return blob.download_as_text(encoding="utf-8")
    except Exception as e:
        _log(f"download error {blob_name}: {e}")
        return None


def _upload_text(blob_name: str, content: str) -> bool:
    if not GCS_BUCKET:
        return False
    try:
        client = _gcs_client()
        blob = client.bucket(GCS_BUCKET).blob(blob_name)
        blob.upload_from_string(content, content_type="application/json")
        _log(f"uploaded {blob_name}")
        return True
    except Exception as e:
        _log(f"upload error {blob_name}: {e}")
        return False


# --------------------------------------------------------------------------- #
# Date/week helpers
# --------------------------------------------------------------------------- #

def _day_key(ts: float) -> str:
    return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")


def _week_key(ts: float) -> str:
    d = datetime.datetime.utcfromtimestamp(ts)
    iso_year, iso_week, _ = d.isocalendar()
    return f"week:{iso_year}-W{iso_week:02d}"


# --------------------------------------------------------------------------- #
# Core aggregation
# --------------------------------------------------------------------------- #

def _ledger_blob(agent_id: str) -> str:
    # Per-agent ledger. Fall back to shared ledger if agent_id is "unknown".
    if agent_id and agent_id != "unknown":
        return f"truclaw/policies/{agent_id}/security-ledger.jsonl"
    return LEDGER_BLOB_PATTERN


def _usage_blob(agent_id: str) -> str:
    return f"truclaw/policies/{agent_id}/usage_summary.json"


def _memory_blob(agent_id: str) -> str:
    return f"truclaw/policies/{agent_id}/memory.md"


def _generate_memory_summary(
    agent_id: str,
    ledger_text: str,
    counts: Dict[str, Any],
) -> str:
    """
    Deterministic qualitative behavioral summary for the classifier.
    No LLM — pure aggregation from ledger + counts.
    Covers the last 7 days per user.
    """
    import datetime as dt

    now = dt.datetime.utcnow()
    cutoff_ts = (now - dt.timedelta(days=7)).timestamp()
    day_keys = [(now - dt.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    # Scan ledger for notable events in the last 7 days
    notable: Dict[str, List[str]] = defaultdict(list)  # userId -> event strings

    for line in ledger_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event: Dict[str, Any] = json.loads(line)
        except Exception:
            continue

        try:
            ts = float(event.get("ts", 0))
        except (TypeError, ValueError):
            continue

        if ts < cutoff_ts:
            continue

        user_id = event.get("userId") or "unknown"
        tool = event.get("toolName") or "unknown"
        allowed = event.get("allowed", True)
        reason = event.get("reason") or ""
        threshold_violation = event.get("thresholdViolation", False)
        dangerous = event.get("dangerous", False)
        safe_bypass = event.get("safeBypass", False)
        ts_str = dt.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

        if not allowed:
            notable[user_id].append(f"- {ts_str}: {tool} BLOCKED — {reason}")
        elif threshold_violation:
            notable[user_id].append(f"- {ts_str}: {tool} threshold exceeded — {reason}")
        elif dangerous and not safe_bypass:
            notable[user_id].append(f"- {ts_str}: {tool} approved after auth — {reason}")

    lines = [
        f"# TruClaw Behavioral Memory — {agent_id}",
        f"Generated: {now.strftime('%Y-%m-%dT%H:%M:%SZ')} | Window: last 7 days",
        "",
    ]

    if not counts:
        lines.append("No activity recorded in this period.")
        return "\n".join(lines)

    for user_id, tools in sorted(counts.items()):
        lines.append(f"## User: {user_id}")

        tool_lines = []
        total = 0
        for tool_name, periods in sorted(tools.items()):
            week_total = sum(periods.get(d, 0) for d in day_keys)
            if week_total == 0:
                continue
            total += week_total
            tool_lines.append(f"  - {tool_name}: {week_total} calls")

        lines.append(f"**7-day total:** {total} tool calls")
        lines.extend(tool_lines)

        user_notable = notable.get(user_id, [])
        if user_notable:
            lines.append("**Notable events:**")
            lines.extend(user_notable[-10:])
        else:
            lines.append("**Notable events:** None — normal activity pattern")

        lines.append("")

    return "\n".join(lines)


def _aggregate_ledger(ledger_text: str) -> Dict[str, Any]:
    """
    Parse JSONL ledger, aggregate per userId → toolName → day/week counts.

    Returns:
    {
      "user:abc": {
        "sync_ask_for_approval": {
          "2026-06-12": 3,
          "week:2026-W24": 11
        }
      }
    }
    """
    # counts[userId][toolName][period] = int
    counts: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )

    for line in ledger_text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event: Dict[str, Any] = json.loads(line)
        except Exception:
            continue

        user_id = event.get("userId") or "unknown"
        tool_name = event.get("toolName")
        ts = event.get("ts")

        if not tool_name or not ts:
            continue

        # Only count allowed calls — blocked calls didn't execute
        if not event.get("allowed", True):
            continue

        # Skip safe-bypass events — they don't count against limits
        if event.get("safeBypass"):
            continue

        try:
            ts_float = float(ts)
        except (TypeError, ValueError):
            continue

        counts[user_id][tool_name][_day_key(ts_float)] += 1
        counts[user_id][tool_name][_week_key(ts_float)] += 1

    # Convert defaultdicts to plain dicts for JSON serialisation
    return {
        uid: {
            tool: dict(periods)
            for tool, periods in tools.items()
        }
        for uid, tools in counts.items()
    }


def _aggregate_agent(agent_id: str) -> bool:
    """Aggregate ledger for one agent. Returns True on success."""
    _log(f"aggregating agentId={agent_id}")

    ledger_text = _download_text(_ledger_blob(agent_id))
    if ledger_text is None:
        # Also try the shared ledger (single-agent deployments)
        ledger_text = _download_text(LEDGER_BLOB_PATTERN)

    if not ledger_text:
        _log(f"no ledger found for agentId={agent_id} — skipping")
        return True  # not an error, just no data yet

    counts = _aggregate_ledger(ledger_text)

    summary = {
        "agentId": agent_id,
        "generatedAt": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": counts,
    }

    content = json.dumps(summary, indent=2, sort_keys=True)
    ok = _upload_text(_usage_blob(agent_id), content)

    # Write qualitative memory summary (non-fatal if it fails)
    try:
        memory_md = _generate_memory_summary(agent_id, ledger_text, counts)
        _upload_text(_memory_blob(agent_id), memory_md)
    except Exception as e:
        _log(f"memory summary generation failed agentId={agent_id}: {e} — skipping")

    return ok


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main() -> int:
    _log(f"starting — bucket={GCS_BUCKET or '(none, dry-run)'}")

    if not GCS_BUCKET:
        _log("TRUCLAW_GCS_BUCKET not set — nothing to do")
        return 0

    agent_ids = _list_agent_ids()

    if not agent_ids:
        # Fallback: single-agent deployment where ledger lives at the
        # shared path (truclaw/security-ledger.jsonl) and agentId is
        # unknown. Try aggregating with agentId="unknown".
        _log("no policy-based agents found; trying shared ledger for agentId=unknown")
        agent_ids = ["unknown"]

    _log(f"agents to aggregate: {agent_ids}")

    errors = 0
    for agent_id in agent_ids:
        try:
            ok = _aggregate_agent(agent_id)
            if not ok:
                errors += 1
        except Exception as e:
            _log(f"unexpected error agentId={agent_id}: {e}")
            errors += 1

    _log(f"done — agents={len(agent_ids)} errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
