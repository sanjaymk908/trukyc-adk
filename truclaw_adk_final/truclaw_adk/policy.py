"""
TruClaw policy management.

Loads TruClaw-Policies.json for the current agent from GCS.
If none exists, bootstraps one from code defaults + agent tool tree,
saves it to GCS, and logs a warning that it needs human review.

GCS path: truclaw/policies/<agentId>/TruClaw-Policies.json
Usage summary path: truclaw/policies/<agentId>/usage_summary.json
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from . import config
from .gcs_storage import GCS_BUCKET, gcs_download, gcs_upload
from .logging import log

# --------------------------------------------------------------------------- #
# Code-level defaults (seeded from the original danger.py constants)
# Domain teams override these in their GitHub-managed TruClaw-Policies.json.
# --------------------------------------------------------------------------- #

_DEFAULT_SAFE_TOOLS: List[str] = [
    "read",
    "session_status",
    "list",
    "ls",
    "web_search",
    "web_fetch",
    "browser_snapshot",
    "status",
    "truclaw_pair",
    "truclaw_status",
    "transfer_to_agent",
    "transfer_to_agent_tool",
    "agent_transfer",
    "load_artifacts",
    "list_artifacts",
    "save_artifacts",
]

_DEFAULT_ALWAYS_DANGEROUS_TOOLS: List[str] = [
    "place_trade",
    "execute_trade",
    "send_email",
    "send_email_via_porteden",
    "delete_email",
    "forward_email",
    "reply_email",
]

_DEFAULT_BUSINESS_RULES = (
    "No specific business rules configured. "
    "All unclassified tool calls will be evaluated by the security classifier. "
    "Update this field with domain-specific policy before deploying to production."
)

# --------------------------------------------------------------------------- #
# In-process cache — loaded once per process per agentId
# --------------------------------------------------------------------------- #

_policy_cache: Dict[str, Dict[str, Any]] = {}
_usage_cache: Dict[str, Dict[str, Any]] = {}


# --------------------------------------------------------------------------- #
# GCS path helpers
# --------------------------------------------------------------------------- #

def _policy_blob(agent_id: str) -> str:
    return f"truclaw/policies/{agent_id}/TruClaw-Policies.json"


def _usage_blob(agent_id: str) -> str:
    return f"truclaw/policies/{agent_id}/usage_summary.json"


def _policy_local(agent_id: str) -> Path:
    return config.STATE_DIR / "policies" / agent_id / "TruClaw-Policies.json"


def _usage_local(agent_id: str) -> Path:
    return config.STATE_DIR / "policies" / agent_id / "usage_summary.json"


# --------------------------------------------------------------------------- #
# Bootstrap: build initial policy from code defaults + live agent tool tree
# --------------------------------------------------------------------------- #

def _discover_agent_tools(agent: Any) -> Set[str]:
    """Walk the agent tree and collect all tool names."""
    found: Set[str] = set()
    seen: Set[int] = set()

    def walk(a: Any) -> None:
        if id(a) in seen:
            return
        seen.add(id(a))
        for t in getattr(a, "tools", None) or []:
            name = getattr(t, "name", None) or getattr(t, "__name__", None)
            if name:
                found.add(name)
        for child in getattr(a, "sub_agents", None) or []:
            walk(child)

    walk(agent)
    return found


def _bootstrap_policy(agent_id: str, agent: Optional[Any] = None) -> Dict[str, Any]:
    """
    Build a starter policy.
    - safeTools / alwaysDangerousTools seeded from code defaults,
      filtered to tools that actually exist on the agent (if agent provided).
    - Everything else goes to unclassified (sent to classifier at runtime).
    """
    safe_set = set(_DEFAULT_SAFE_TOOLS)
    dangerous_set = set(_DEFAULT_ALWAYS_DANGEROUS_TOOLS)

    if agent is not None:
        live_tools = _discover_agent_tools(agent)
        log(f"[policy] agent tree discovered tools: {sorted(live_tools)}")
        unclassified = sorted(live_tools - safe_set - dangerous_set)
        # Only include tools that actually exist on this agent
        agent_safe = sorted(safe_set & live_tools)
        agent_dangerous = sorted(dangerous_set & live_tools)
    else:
        unclassified = []
        agent_safe = sorted(safe_set)
        agent_dangerous = sorted(dangerous_set)

    policy = {
        "agentId": agent_id,
        "version": "1.0.0",
        "bootstrappedFromCode": True,
        "bootstrappedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "safeTools": agent_safe,
        "alwaysDangerousTools": agent_dangerous,
        "unclassified": unclassified,
        "toolThresholds": {},
        "businessRules": _DEFAULT_BUSINESS_RULES,
    }
    log(
        f"[policy] bootstrapped agentId={agent_id} "
        f"safe={len(agent_safe)} dangerous={len(agent_dangerous)} "
        f"unclassified={len(unclassified)}"
    )
    return policy


# --------------------------------------------------------------------------- #
# Load / save
# --------------------------------------------------------------------------- #

def _save_policy(agent_id: str, policy: Dict[str, Any]) -> None:
    local = _policy_local(agent_id)
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(json.dumps(policy, indent=2), encoding="utf-8")
    gcs_upload(local, _policy_blob(agent_id))
    log(f"[policy] saved agentId={agent_id} version={policy.get('version')}")


def load_policy(agent_id: str, agent: Optional[Any] = None) -> Dict[str, Any]:
    """
    Load policy for agent_id.  Order:
      1. In-process cache
      2. Local file (already downloaded this process run)
      3. GCS
      4. Bootstrap from code defaults (saves to GCS for admin review)
    """
    if agent_id in _policy_cache:
        return _policy_cache[agent_id]

    local = _policy_local(agent_id)

    # Try GCS download if local doesn't exist yet
    if not local.exists():
        gcs_download(local, _policy_blob(agent_id))

    if local.exists():
        try:
            policy = json.loads(local.read_text(encoding="utf-8"))
            _policy_cache[agent_id] = policy
            log(
                f"[policy] loaded from disk agentId={agent_id} "
                f"version={policy.get('version')} "
                f"safe={len(policy.get('safeTools', []))} "
                f"dangerous={len(policy.get('alwaysDangerousTools', []))} "
                f"unclassified={len(policy.get('unclassified', []))}"
            )
            return policy
        except Exception as e:
            log(f"[policy] corrupt policy file agentId={agent_id}: {e} — bootstrapping")

    # Nothing in GCS either — bootstrap
    log(f"[policy] no policy found for agentId={agent_id} — bootstrapping from code defaults")
    policy = _bootstrap_policy(agent_id, agent)
    _save_policy(agent_id, policy)
    log(
        f"[policy] NOTICE: bootstrapped policy saved to GCS for agentId={agent_id}. "
        f"Review and customise gs://{GCS_BUCKET}/{_policy_blob(agent_id)} "
        f"then redeploy."
    )
    _policy_cache[agent_id] = policy
    return policy


def reload_policy(agent_id: str) -> Dict[str, Any]:
    """Force reload from GCS, bypassing cache. Used by admin routes."""
    _policy_cache.pop(agent_id, None)
    local = _policy_local(agent_id)
    if local.exists():
        local.unlink()
    return load_policy(agent_id)


# --------------------------------------------------------------------------- #
# Usage summary (pre-aggregated by cron, read-only at runtime)
# --------------------------------------------------------------------------- #

def load_usage_summary(agent_id: str) -> Dict[str, Any]:
    """
    Load the pre-aggregated usage summary written by the cron aggregator.
    Returns empty dict if not yet generated.
    Cached in-process; call reload_usage_summary() to refresh.
    """
    if agent_id in _usage_cache:
        return _usage_cache[agent_id]

    local = _usage_local(agent_id)
    if not local.exists():
        gcs_download(local, _usage_blob(agent_id))

    if local.exists():
        try:
            summary = json.loads(local.read_text(encoding="utf-8"))
            _usage_cache[agent_id] = summary
            log(
                f"[policy] usage summary loaded agentId={agent_id} "
                f"generatedAt={summary.get('generatedAt')} "
                f"users={len(summary.get('counts', {}))}"
            )
            return summary
        except Exception as e:
            log(f"[policy] usage summary load error agentId={agent_id}: {e}")

    return {}


def reload_usage_summary(agent_id: str) -> Dict[str, Any]:
    """Force reload from GCS. Called at process startup and by cron ping."""
    _usage_cache.pop(agent_id, None)
    local = _usage_local(agent_id)
    if local.exists():
        local.unlink()
    return load_usage_summary(agent_id)


# --------------------------------------------------------------------------- #
# Threshold check helpers (called from danger.py)
# --------------------------------------------------------------------------- #

def _week_key(ts: Optional[float] = None) -> str:
    import datetime
    d = datetime.datetime.utcfromtimestamp(ts or time.time())
    iso_year, iso_week, _ = d.isocalendar()
    return f"week:{iso_year}-W{iso_week:02d}"


def _day_key(ts: Optional[float] = None) -> str:
    import datetime
    d = datetime.datetime.utcfromtimestamp(ts or time.time())
    return d.strftime("%Y-%m-%d")


def check_threshold(
    agent_id: str,
    user_id: str,
    tool_name: str,
    tool_args: Dict[str, Any],
) -> Optional[str]:
    """
    Check toolThresholds from the policy.
    Returns a violation reason string if any limit is exceeded, else None.

    Checks (in order):
      1. safeBelow — single-call field value threshold
      2. dailyLimit — from usage_summary
      3. weeklyLimit — from usage_summary
      4. perSessionLimit — from usage_summary (session counts not yet tracked;
         reserved for future use)
    """
    policy = _policy_cache.get(agent_id, {})
    thresholds = policy.get("toolThresholds", {})
    if not thresholds or tool_name not in thresholds:
        return None

    rule = thresholds[tool_name]

    # 1. safeBelow — check the value in this specific call's args
    field = rule.get("field")
    safe_below = rule.get("safeBelow")
    if field and safe_below is not None:
        val = tool_args.get(field) if isinstance(tool_args, dict) else None
        if val is not None:
            try:
                if float(val) >= float(safe_below):
                    return (
                        f"tool={tool_name} field={field} value={val} "
                        f"exceeds safeBelow={safe_below}"
                    )
            except (TypeError, ValueError):
                pass

    # 2 & 3. dailyLimit / weeklyLimit — from pre-aggregated usage summary
    daily_limit = rule.get("dailyLimit")
    weekly_limit = rule.get("weeklyLimit")

    if daily_limit is None and weekly_limit is None:
        return None

    summary = _usage_cache.get(agent_id, {})
    user_counts = summary.get("counts", {}).get(user_id, {}).get(tool_name, {})

    if daily_limit is not None:
        day_count = user_counts.get(_day_key(), 0)
        if day_count >= int(daily_limit):
            return (
                f"tool={tool_name} userId={user_id} "
                f"dailyCount={day_count} exceeds dailyLimit={daily_limit}"
            )

    if weekly_limit is not None:
        week_count = user_counts.get(_week_key(), 0)
        if week_count >= int(weekly_limit):
            return (
                f"tool={tool_name} userId={user_id} "
                f"weeklyCount={week_count} exceeds weeklyLimit={weekly_limit}"
            )

    return None
