import os
import asyncio
import json
from fastapi import Request
from fastapi.responses import JSONResponse
import httpx
from .logging import log

ADK_APP_NAME = os.getenv("ADK_APP_NAME", "orchestrator")
ADK_BASE_URL = os.getenv("ADK_BASE_URL", "http://localhost:8080")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")


async def _get_chat_access_token() -> str:
    """Get OAuth2 access token for Google Chat API using service account."""
    import time
    import json
    import base64

    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON not configured")

    sa = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)

    # build JWT
    now = int(time.time())
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()

    payload = base64.urlsafe_b64encode(json.dumps({
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/chat.bot",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }).encode()).rstrip(b"=").decode()

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend

    private_key = serialization.load_pem_private_key(
        sa["private_key"].encode(),
        password=None,
        backend=default_backend()
    )

    signing_input = f"{header}.{payload}".encode()
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    sig_b64 = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()

    jwt_token = f"{header}.{payload}.{sig_b64}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token,
            }
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def _post_chat_message(space_name: str, thread_name: str, text: str) -> None:
    """Post a message to Google Chat space via REST API."""
    try:
        token = await _get_chat_access_token()
        space_id = space_name.replace("spaces/", "")
        url = f"https://chat.googleapis.com/v1/spaces/{space_id}/messages"

        payload = {
            "text": text,
            "thread": {"name": thread_name},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            log(f"[chat] posted reply to {space_name}")
    except Exception as e:
        log(f"[chat] failed to post reply: {e}")


async def _ensure_session(user_id: str, session_id: str) -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            await client.post(
                f"{ADK_BASE_URL}/apps/{ADK_APP_NAME}/users/{user_id}/sessions/{session_id}",
                headers={"Content-Type": "application/json"},
                json={},
            )
        except Exception as e:
            log(f"[chat] session create error: {e}")


async def _run_agent(user_id: str, session_id: str, text: str) -> str:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{ADK_BASE_URL}/run",
            headers={"Content-Type": "application/json"},
            json={
                "appName": ADK_APP_NAME,
                "userId": user_id,
                "sessionId": session_id,
                "newMessage": {
                    "role": "user",
                    "parts": [{"text": text}],
                },
            },
        )
        resp.raise_for_status()
        events = resp.json()

    for event in reversed(events):
        content = event.get("content", {})
        if content.get("role") == "model":
            parts = content.get("parts", [])
            text_parts = [p.get("text", "") for p in parts if p.get("text")]
            if text_parts:
                return "\n".join(text_parts)

    return "I processed your request but have no response to share."


async def _process_and_send(
    user_id: str,
    session_id: str,
    text: str,
    space_name: str,
    thread_name: str,
) -> None:
    """Process agent request and post reply via Chat API."""
    try:
        await _ensure_session(user_id, session_id)
        reply = await _run_agent(user_id, session_id, text)
    except Exception as e:
        log(f"[chat] agent error userId={user_id} error={e}")
        reply = f"Sorry, I encountered an error: {e}"

    log(f"[chat] reply preview: {reply[:100]}")
    await _post_chat_message(space_name, thread_name, reply)


def register_chat_handler(app) -> None:

    @app.post("/chat")
    async def chat_webhook(request: Request):
        raw = await request.body()
        log(f"[chat] raw bytes: {raw[:200]}")

        try:
            body = await request.json()
        except Exception as e:
            log(f"[chat] json parse error: {e}")
            return JSONResponse({})

        log(f"[chat] raw body: {str(body)[:500]}")

        event_type = body.get("type")
        log(f"[chat] event_type={event_type}")

        if event_type == "ADDED_TO_SPACE":
            return JSONResponse({
                "text": (
                    "👋 TruClaw agent ready.\n\n"
                    "Say *pair my TruClaw device* to set up biometric authorization, "
                    "or ask me anything."
                )
            })

        if event_type == "REMOVED_FROM_SPACE":
            return JSONResponse({})

        if event_type == "MESSAGE":
            message = body.get("message", {})
            text = message.get("text", "").strip()
            if not text:
                return JSONResponse({"text": "Please send a text message."})

            sender = body.get("user", {})
            raw_user_id = sender.get("name", "default")
            user_id = raw_user_id.replace("/", "_")

            space_name = body.get("space", {}).get("name", "spaces/default")
            thread_name = message.get("thread", {}).get("name", "")
            session_id = f"{space_name}_{thread_name}".replace("/", "_")

            log(f"[chat] userId={user_id} sessionId={session_id} text={text[:80]}")

            # ack immediately to prevent Chat retry
            asyncio.create_task(_process_and_send(
                user_id, session_id, text, space_name, thread_name
            ))
            return JSONResponse({})

        return JSONResponse({})

    log("[chat_handler] /chat route registered")
