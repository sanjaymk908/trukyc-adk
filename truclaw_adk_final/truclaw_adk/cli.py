import argparse
import asyncio
import json
import os
import site
import sys
from pathlib import Path

from .logging import log
from .pairing import (
    start_pairing,
    poll_for_pairing,
    save_pairing,
    load_paired_devices,
)


PTH_NAME = "zzz_truclaw_adk_autopatch.pth"
PTH_LINE = "import truclaw_adk.autopatch\n"


def _site_packages_dir() -> Path:
    candidates = site.getsitepackages()
    if not candidates:
        raise RuntimeError("Could not find site-packages")

    for c in candidates:
        p = Path(c)
        if p.exists():
            return p

    return Path(candidates[0])


def cmd_install(args) -> int:
    site_packages = _site_packages_dir()
    pth_path = site_packages / PTH_NAME

    pth_path.write_text(PTH_LINE, encoding="utf-8")

    log(f"[install] wrote autopatch file path={pth_path}")
    log("[install] TruClaw ADK guardrail will load automatically on Python startup")
    return 0


def cmd_doctor(args) -> int:
    ok = True

    site_packages = _site_packages_dir()
    pth_path = site_packages / PTH_NAME

    print("TruClaw ADK Doctor")
    print("------------------")
    print(f"python: {sys.executable}")
    print(f"site-packages: {site_packages}")
    print(f"autopatch: {'installed' if pth_path.exists() else 'missing'}")
    print(f"TRUKYC_RELAY_URL: {'set' if os.getenv('TRUKYC_RELAY_URL') else 'missing'}")
    print(f"ANTHROPIC_API_KEY_TRUKYC: {'set' if os.getenv('ANTHROPIC_API_KEY_TRUKYC') else 'missing'}")
    print(f"TRUCLAW_STATE_DIR: {os.getenv('TRUCLAW_STATE_DIR', './.truclaw')}")

    if not pth_path.exists():
        ok = False
    if not os.getenv("TRUKYC_RELAY_URL"):
        ok = False
    if not os.getenv("ANTHROPIC_API_KEY_TRUKYC"):
        ok = False

    devices = load_paired_devices()
    print(f"paired devices: {len(devices)}")

    return 0 if ok else 2


def cmd_status(args) -> int:
    devices = load_paired_devices()

    if not devices:
        log("[status] no paired devices")
        return 0

    print(json.dumps(devices, indent=2))
    return 0


def cmd_pair(args) -> int:
    async def run_pair() -> int:
        result = await start_pairing(start_background_poll=False)

        print(json.dumps(result, indent=2))

        if result.get("status") != "pairing_started":
            log("[pair] failed to start pairing")
            return 2

        session_id = result["sessionId"]

        log(f"[pair] waiting for mobile client sessionId={session_id}")

        data = await poll_for_pairing(session_id)

        if not data:
            log(f"[pair] timeout waiting for pairing sessionId={session_id}")
            return 2

        save_pairing(session_id, data)

        log(f"[pair] pairing complete sessionId={session_id}")

        return 0

    return asyncio.run(run_pair())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="truclaw",
        description="TruClaw ADK protection",
    )

    sub = parser.add_subparsers(dest="command")

    install_p = sub.add_parser("install")
    install_p.set_defaults(func=cmd_install)

    doctor_p = sub.add_parser("doctor")
    doctor_p.set_defaults(func=cmd_doctor)

    pair_p = sub.add_parser("pair")
    pair_p.set_defaults(func=cmd_pair)

    status_p = sub.add_parser("status")
    status_p.set_defaults(func=cmd_status)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except KeyboardInterrupt:
        log("[cli] interrupted")
        return 130
