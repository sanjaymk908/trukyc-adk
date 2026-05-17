import os
from fastapi import Request
from fastapi.responses import JSONResponse
import httpx
from .logging import log

ADK_APP_NAME = os.getenv("ADK_APP_NAME", "orchestrator")
ADK_BASE_URL = os.getenv("ADK_BASE_URL", "http://localhost:8080")


async def _ensure_session(user_id: str, session_id: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                f"{ADK_BASE_URL}/apps/{ADK_APP_NAME}/users/{user_id}/sessions/{session_id}",
                headers={"Content-Type": "application/json"},
                json={},
            )
        except Exception as e:
            log(f"[chat] session create error: {e}")


async def _run_agent(user_id: str, session_id: str, text: str) -> str:
    async with httpx.AsyncClient(timeout=25.0) as client:
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


def register_chat_handler(app) -> None:

    @app.post("/chat")
    async def chat_webhook(request: Request):
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({})

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

            space = body.get("space", {}).get("name", "space_default")
            thread = message.get("thread", {}).get("name", "thread_default")
            session_id = f"{space}_{thread}".replace("/", "_")

            log(f"[chat] userId={user_id} sessionId={session_id} text={text[:80]}")

            try:
                await _ensure_session(user_id, session_id)
                reply = await _run_agent(user_id, session_id, text)
            except Exception as e:
                log(f"[chat] agent error userId={user_id} error={e}")
                reply = f"Sorry, I encountered an error: {e}"

            return JSONResponse({"text": reply})

        return JSONResponse({})

    log("[chat_handler] /chat route registered")
