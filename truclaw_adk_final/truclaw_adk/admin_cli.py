#!/usr/bin/env python3
"""
TruClaw Admin CLI — for admin use only.
Usage:
  python -m truclaw_adk.admin_cli clear-ledger
  python -m truclaw_adk.admin_cli clear-memory
  python -m truclaw_adk.admin_cli clear-all
  python -m truclaw_adk.admin_cli view-ledger [--limit N]
  python -m truclaw_adk.admin_cli view-memory
"""

import sys
import os
import hashlib


def _require_admin_key() -> None:
    """
    Validates TRUCLAW_ADMIN_KEY provided at runtime against
    TRUCLAW_ADMIN_KEY_HASH stored on the server in Cloud Run env vars.

    Admin passes TRUCLAW_ADMIN_KEY at runtime — it never gets stored.
    Server stores only TRUCLAW_ADMIN_KEY_HASH — set once via admin.sh setup-key.

    To generate hash manually:
      python3 -c "import hashlib; print(hashlib.sha256(b'your-key').hexdigest())"
    """
    provided = os.getenv("TRUCLAW_ADMIN_KEY", "").strip()
    expected_hash = os.getenv("TRUCLAW_ADMIN_KEY_HASH", "").strip()

    if not provided:
        print("ERROR: TRUCLAW_ADMIN_KEY not set.")
        print("  Usage: TRUCLAW_ADMIN_KEY=your-key ./admin.sh <command>")
        sys.exit(1)

    if not expected_hash:
        print("ERROR: Server is not configured with TRUCLAW_ADMIN_KEY_HASH.")
        print("  Run: ./admin.sh setup-key")
        sys.exit(1)

    if hashlib.sha256(provided.encode()).hexdigest() != expected_hash:
        print("ERROR: Invalid admin key.")
        sys.exit(1)


def cmd_clear_ledger() -> None:
    _require_admin_key()
    from truclaw_adk.ledger import clear_ledger
    clear_ledger()
    print("✅ Ledger cleared.")


def cmd_clear_memory() -> None:
    _require_admin_key()
    from truclaw_adk.ledger import clear_memory
    clear_memory()
    print("✅ Memory cleared.")


def cmd_clear_all() -> None:
    _require_admin_key()
    from truclaw_adk.ledger import clear_all
    clear_all()
    print("✅ Ledger and memory cleared.")


def cmd_view_ledger(limit: int = 20) -> None:
    _require_admin_key()
    from truclaw_adk.ledger import read_events
    events = read_events(limit)
    if not events:
        print("No events in ledger.")
        return
    import json
    for e in events:
        print(json.dumps(e, indent=2, default=str))


def cmd_view_memory() -> None:
    _require_admin_key()
    from truclaw_adk.ledger import MEMORY_PATH, _ensure_memory_loaded
    _ensure_memory_loaded()
    if not MEMORY_PATH.exists():
        print("No memory file.")
        return
    print(MEMORY_PATH.read_text(encoding="utf-8"))


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    cmd = args[0]

    if cmd == "clear-ledger":
        cmd_clear_ledger()
    elif cmd == "clear-memory":
        cmd_clear_memory()
    elif cmd == "clear-all":
        cmd_clear_all()
    elif cmd == "view-ledger":
        limit = int(args[2]) if len(args) > 2 and args[1] == "--limit" else 20
        cmd_view_ledger(limit)
    elif cmd == "view-memory":
        cmd_view_memory()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
