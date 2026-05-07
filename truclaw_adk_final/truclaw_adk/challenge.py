import asyncio
import hashlib
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict

import httpx

from . import config
from .pairing import find_paired_device
from .jwt_verify import verify_jwt
from .logging import log


PENDING: Dict[str, Dict[str, Any]] = {}


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _make_challenge_session_id(nonce: str, timestamp: str) -> str:
    return hashlib.sha256(
        f"{nonce}{timestamp}".encode("utf-8")
    ).hexdigest()[:16]


async def send_challenge(
    action: str,
    reason: str,
    tool_name: str,
    tool_args: Any,
) -> Dict[str, Any]:
    found = find_paired_device()

    if not found:
        log("[challenge] no paired device found; block")
        return {
            "approved": False,
            "reason": "no paired TruClaw device found",
        }

    paired_session_id, device = found

    fcm_token = device.get("fcmToken")
    if not fcm_token:
        log(f"[challenge] paired device missing fcmToken pairedSessionId={paired_session_id}")
        return {
            "approved": False,
            "reason": "paired device missing fcmToken",
        }

    if not config.RELAY_URL:
        return {
            "approved": False,
            "reason": "TRUKYC_RELAY_URL not set",
        }

    nonce = secrets.token_hex(16)
    timestamp = _now_iso()
    salt = secrets.token_hex(8)

    # IMPORTANT:
    # This mirrors OpenClaw src/challenge.ts.
    # This is NOT the pairing session id.
    # This is the challenge session id used by:
    #   webhookURL = /verify/<challenge_session_id>
    #   polling    = /poll/<challenge_session_id>
    challenge_session_id = _make_challenge_session_id(
        nonce,
        timestamp,
    )

    expires_at = int(time.time() + config.CHALLENGE_TIMEOUT_SECONDS)

    webhook_url = f"{config.RELAY_URL}/verify/{challenge_session_id}"
    challenge_url = f"{config.RELAY_URL}/challenge"

    payload = {
        "fcmToken": fcm_token,
        "nonce": nonce,
        "timestamp": timestamp,
        "salt": salt,
        "sessionId": challenge_session_id,
        "webhookURL": webhook_url,
        "action": action,
    }

    PENDING[challenge_session_id] = {
        "nonce": nonce,
        "timestamp": timestamp,
        "salt": salt,
        "pairedSessionId": paired_session_id,
        "challengeSessionId": challenge_session_id,
        "expiresAt": expires_at,
        "toolName": tool_name,
        "toolArgs": tool_args,
        "action": action,
        "reason": reason,
    }

    log("[challenge] ── New challenge ──")
    log(f"[challenge] pairedSessionId={paired_session_id}")
    log(f"[challenge] challengeSessionId={challenge_session_id}")
    log(f"[challenge] nonce={nonce}")
    log(f"[challenge] toolName={tool_name}")
    log(f"[challenge] action={action}")
    log(f"[challenge] webhookURL={webhook_url}")
    log(f"[challenge] POST {challenge_url}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                challenge_url,
                headers={"Content-Type": "application/json"},
                json=payload,
            )

        text = resp.text[:500]
        log(f"[challenge] relay response status={resp.status_code} body={text}")

        if resp.status_code >= 400:
            PENDING.pop(challenge_session_id, None)
            return {
                "approved": False,
                "reason": f"relay error {resp.status_code}",
                "relayBody": text,
                "challengeSessionId": challenge_session_id,
            }

    except Exception as e:
        PENDING.pop(challenge_session_id, None)
        log(f"[challenge] relay exception error={e}")
        return {
            "approved": False,
            "reason": f"relay exception: {e}",
            "challengeSessionId": challenge_session_id,
        }

    return await poll_for_approval(challenge_session_id)


async def poll_for_approval(
    challenge_session_id: str,
) -> Dict[str, Any]:
    pending = PENDING.get(challenge_session_id)

    if not pending:
        return {
            "approved": False,
            "reason": "challenge not pending",
            "challengeSessionId": challenge_session_id,
        }

    poll_url = f"{config.RELAY_URL}/poll/{challenge_session_id}"

    log(
        f"[challenge] polling relay for JWT "
        f"challengeSessionId={challenge_session_id} url={poll_url}"
    )

    interval = 0.5
    max_interval = 3.0
    backoff = 1.5

    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.time() < pending["expiresAt"]:
            try:
                resp = await client.get(poll_url)

                if resp.status_code == 200:
                    data = resp.json()
                    jwt = data.get("jwt")

                    if not jwt:
                        PENDING.pop(challenge_session_id, None)
                        return {
                            "approved": False,
                            "reason": "approval missing JWT",
                            "challengeSessionId": challenge_session_id,
                        }

                    log(
                        f"[challenge] JWT received "
                        f"challengeSessionId={challenge_session_id}"
                    )

                    verified = verify_jwt(
                        jwt,
                        pending["nonce"],
                        # OpenClaw verifies nonce against the challenge session's JWT.
                        # The JWT claims sessionId is the mobile/KYC session id,
                        # so do NOT force it to equal challenge_session_id here.
                        None,
                    )

                    if not verified.get("valid"):
                        PENDING.pop(challenge_session_id, None)
                        log(
                            f"[challenge] JWT invalid "
                            f"challengeSessionId={challenge_session_id} "
                            f"error={verified.get('error')}"
                        )
                        return {
                            "approved": False,
                            "reason": verified.get("error"),
                            "challengeSessionId": challenge_session_id,
                            "jwt": verified,
                        }

                    claims = verified.get("claims", {})

                    if claims.get("isHuman") is False:
                        PENDING.pop(challenge_session_id, None)
                        return {
                            "approved": False,
                            "reason": "JWT isHuman=false",
                            "challengeSessionId": challenge_session_id,
                            "claims": claims,
                        }

                    PENDING.pop(challenge_session_id, None)

                    log(
                        f"[challenge] approved "
                        f"challengeSessionId={challenge_session_id}"
                    )

                    return {
                        "approved": True,
                        "challengeSessionId": challenge_session_id,
                        "claims": claims,
                        "sessionId": verified.get("sessionId"),
                    }

                if resp.status_code == 202:
                    log(
                        f"[challenge] pending "
                        f"challengeSessionId={challenge_session_id} "
                        f"interval={interval:.1f}s"
                    )

                elif resp.status_code == 404:
                    log(
                        f"[challenge] poll 404 "
                        f"challengeSessionId={challenge_session_id}"
                    )

                else:
                    log(
                        f"[challenge] unexpected poll status={resp.status_code} "
                        f"body={resp.text[:300]}"
                    )

            except Exception as e:
                log(
                    f"[challenge] poll error "
                    f"challengeSessionId={challenge_session_id} error={e}"
                )

            await asyncio.sleep(interval)
            interval = min(interval * backoff, max_interval)

    PENDING.pop(challenge_session_id, None)

    log(f"[challenge] timeout challengeSessionId={challenge_session_id}")

    return {
        "approved": False,
        "reason": "approval timeout",
        "challengeSessionId": challenge_session_id,
    }
