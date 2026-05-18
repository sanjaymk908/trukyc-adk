import os
import asyncio
from fastapi import Request
from fastapi.responses import JSONResponse
import httpx
from .logging import log

ADK_APP_NAME = os.getenv("ADK_APP_NAME", "orchestrator")
ADK_BASE_URL = os.getenv("ADK_BASE_URL", "http://localhost:8080")


def _get_chat_access_token_sync() -> str:
    """Get OAuth2 access token using Application Default Credentials."""
    try:
        import google.auth
        import google.auth.transport.requests

        log("[chat] getting ADC token...")
        credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/chat.bot"]
        )
        log(f"[chat] ADC project={project} credentials_type={type(credentials).__name__}")
        auth_req = google.auth.transport.requests.Request()
        credentials.refresh(auth_req)
        log(f"[chat] token obtained valid={credentials.valid} expiry={credentials.expiry}")
        return credentials.token
    except Exception as e:
        log(f"[chat] failed to get ADC token: {type(e).__name__}: {e}")
        raise


async def _post_chat_message(space_name: str, thread_name: str, text: str) -> None:
    """Post a message to Google Chat space via REST API."""
    log(f"[chat] _post_chat_message space={space_name} thread={thread_name}")
    try:
        token = await asyncio.get_event_loop().run_in_executor(
            None, _get_chat_access_token_sync
        )
        log(f"[chat] token acquired length={len(token) if token else 0}")

        space_id = space_name.replace("spaces/", "")
        url = (
            f"https://chat.googleapis.com/v1/spaces/{space_id}/messages"
            f"?messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"
        )
        log(f"[chat] posting to url={url}")

        payload = {"text": text}
        if thread_name:
            payload["thread"] = {"name": thread_name}
        log(f"[chat] payload={str(payload)[:200]}")

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            log(f"[chat] post status={resp.status_code} body={resp.text}")
            resp.raise_for_status()
            log(f"[chat] posted reply successfully to {space_name}")
    except httpx.HTTPStatusError as e:
        log(f"[chat] HTTP error posting reply: status={e.response.status_code} body={e.response.text}")
    except httpx.TimeoutException as e:
        log(f"[chat] timeout posting reply: {e}")
    except Exception as e:
        log(f"[chat] unexpected error posting reply: {type(e).__name__}: {e}")


async def _ensure_session(user_id: str, session_id: str) -> None:
    log(f"[chat] ensuring session userId={user_id} sessionId={session_id}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{ADK_BASE_URL}/apps/{ADK_APP_NAME}/users/{user_id}/sessions/{session_id}",
                headers={"Content-Type": "application/json"},
                json={},
            )
            log(f"[chat] session status={resp.status_code}")
        except Exception as e:
            log(f"[chat] session create error: {type(e).__name__}: {e}")


async def _run_agent(user_id: str, session_id: str, text: str) -> str:
    log(f"[chat] running agent userId={user_id} sessionId={session_id}")
    try:
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
            log(f"[chat] agent run status={resp.status_code}")
            resp.raise_for_status()
            events = resp.json()
            log(f"[chat] agent returned {len(events)} events")
    except Exception as e:
        log(f"[chat] agent run error: {type(e).__name__}: {e}")
        raise

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
    log(f"[chat] _process_and_send started userId={user_id}")
    try:
        await _ensure_session(user_id, session_id)
        reply = await _run_agent(user_id, session_id, text)
    except Exception as e:
        log(f"[chat] agent error userId={user_id} error={type(e).__name__}: {e}")
        reply = f"Sorry, I encountered an error: {e}"

    log(f"[chat] reply preview: {reply[:100]}")
    await _post_chat_message(space_name, thread_name, reply)
    log(f"[chat] _process_and_send complete userId={user_id}")


def register_chat_handler(app) -> None:

    @app.post("/chat")
    async def chat_webhook(request: Request):
        raw = await request.body()
        log(f"[chat] raw bytes: {raw[:200]}")

        try:
            body = await request.json()
        except Exception as e:
            log(f"[chat] json parse error: {type(e).__name__}: {e}")
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
