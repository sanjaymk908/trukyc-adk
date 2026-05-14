from fastapi import Request
from fastapi.responses import HTMLResponse
from .pairing import start_pairing
from .logging import log

import asyncio

def register_pair_route(app) -> None:
    @app.get("/pair", response_class=HTMLResponse)
    async def pair(request: Request):
        result = await start_pairing(start_background_poll=True)

        if result.get("status") == "error":
            return HTMLResponse(
                content=f"<h2>Error: {result.get('reason')}</h2>",
                status_code=500
            )

        pairing_link = result["pairingLink"]
        qr_url = result["qrImageUrl"]
        session_id = result["sessionId"]

        log(f"[pair_route] serving pairing page sessionId={session_id}")

        return f"""
        <html>
        <head>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>Pair TruClaw</title>
        </head>
        <body style="font-family:sans-serif;text-align:center;padding:40px;max-width:500px;margin:0 auto">
          <h2>📱 Pair TruClaw</h2>
          <p>Scan with the TruClaw app, or tap the link on your iPhone:</p>
          <img src="{qr_url}" width="300" height="300" style="border:1px solid #ddd;padding:8px"/><br><br>
          <a href="{pairing_link}" style="font-size:18px;display:block;margin:16px 0">
            Open in TruClaw ↗
          </a>
          <details style="margin-top:24px;text-align:left">
            <summary style="cursor:pointer;color:#888">Session details</summary>
            <code style="font-size:11px;word-break:break-all;display:block;margin-top:8px">
              sessionId: {session_id}<br>
              pairingLink: {pairing_link}
            </code>
          </details>
        </body>
        </html>
        """

    log("[pair_route] /pair route registered")
