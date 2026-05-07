import asyncio
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

import httpx

from .logging import log


TRUCLAW_STATE_DIR = Path(os.getenv("TRUCLAW_STATE_DIR", "./.truclaw"))

PAIRED_PATH = TRUCLAW_STATE_DIR / "devices" / "paired.json"

RELAY_URL = os.getenv("TRUKYC_RELAY_URL", "").rstrip("/")

PAIRING_DEEPLINK_BASE = os.getenv(
    "TRUCLAW_PAIRING_DEEPLINK_BASE",
    "https://aasa.trusources.ai/openclaw",
)


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def load_paired_devices() -> Dict[str, Dict[str, Any]]:
    if not PAIRED_PATH.exists():
        return {}

    with PAIRED_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Invalid paired devices file: {PAIRED_PATH}")

    return data


def save_paired_devices(devices: Dict[str, Dict[str, Any]]) -> None:
    PAIRED_PATH.parent.mkdir(parents=True, exist_ok=True)

    tmp = PAIRED_PATH.with_suffix(".tmp")

    with tmp.open("w", encoding="utf-8") as f:
        json.dump(devices, f, indent=2, sort_keys=True)

    tmp.replace(PAIRED_PATH)


def save_pairing(session_id: str, data: Dict[str, Any]) -> None:
    required = ["publicKey", "apnsToken", "fcmToken", "platform"]

    missing = [k for k in required if not data.get(k)]
    if missing:
        raise ValueError(f"Missing pairing fields: {missing}")

    devices = load_paired_devices()

    devices[session_id] = {
        "publicKey": data["publicKey"],
        "apnsToken": data["apnsToken"],
        "fcmToken": data["fcmToken"],
        "platform": data["platform"],
        "pairedAt": _now_iso(),
    }

    save_paired_devices(devices)

    log(f"[pair] saved pairing sessionId={session_id}")


def find_paired_device() -> Optional[Tuple[str, Dict[str, Any]]]:
    devices = load_paired_devices()

    for session_id, device in devices.items():
        if device.get("fcmToken") or device.get("apnsToken"):
            return session_id, device

    return None


async def poll_for_pairing(
    session_id: str,
    timeout_seconds: int = 300,
    poll_interval: float = 2.0,
) -> Optional[Dict[str, Any]]:
    if not RELAY_URL:
        raise ValueError("TRUKYC_RELAY_URL is not configured")

    url = f"{RELAY_URL}/pair-poll/{session_id}"

    deadline = asyncio.get_event_loop().time() + timeout_seconds

    log(f"[pair] polling relay sessionId={session_id} url={url}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            if asyncio.get_event_loop().time() > deadline:
                return None

            try:
                resp = await client.get(url)

                if resp.status_code in {204, 404}:
                    await asyncio.sleep(poll_interval)
                    continue

                resp.raise_for_status()

                data = resp.json()

                if data and data.get("publicKey"):
                    log(f"[pair] pairing received sessionId={session_id}")
                    return data

            except Exception as e:
                log(f"[pair] poll error sessionId={session_id} error={e}")

            await asyncio.sleep(poll_interval)


async def start_pairing(start_background_poll: bool = True) -> Dict[str, Any]:
    if not RELAY_URL:
        return {
            "status": "error",
            "reason": "TRUKYC_RELAY_URL not configured",
        }

    session_id = secrets.token_hex(16)

    webhook_url = f"{RELAY_URL}/pair/{session_id}"

    pairing_link = (
        f"{PAIRING_DEEPLINK_BASE}"
        f"?sessionId={session_id}"
        f"&webhookURL={quote(webhook_url)}"
    )

    qr_url = (
        "https://api.qrserver.com/v1/create-qr-code/"
        f"?size=300x300&data={quote(pairing_link)}"
    )

    log(f"[pair] started sessionId={session_id} webhookURL={webhook_url}")

    if start_background_poll:
        async def bg() -> None:
            data = await poll_for_pairing(session_id)
            if data:
                save_pairing(session_id, data)

        asyncio.create_task(bg())

    return {
        "status": "pairing_started",
        "sessionId": session_id,
        "pairingLink": pairing_link,
        "qrImageUrl": qr_url,
        "webhookURL": webhook_url,
    }
