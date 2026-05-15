from fastapi import Request
from fastapi.responses import HTMLResponse
from .pairing import start_pairing, load_paired_devices
from .logging import log


def register_pair_route(app) -> None:

    @app.get("/pair", response_class=HTMLResponse)
    async def pair(request: Request, userId: str = "default"):
        result = await start_pairing(user_id=userId, start_background_poll=True)

        if result.get("status") == "error":
            return HTMLResponse(
                content=f"<h2>Error: {result.get('reason')}</h2>",
                status_code=500
            )

        pairing_link = result["pairingLink"]
        qr_url = result["qrImageUrl"]
        session_id = result["sessionId"]

        log(f"[pair_route] serving pairing page userId={userId} sessionId={session_id}")

        return f"""
        <html>
        <head>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>Pair TruClaw</title>
        </head>
        <body style="font-family:sans-serif;text-align:center;padding:40px;max-width:500px;margin:0 auto">
          <h2>📱 Pair TruClaw</h2>
          <p>Pairing as <strong>{userId}</strong></p>
          <p>Scan with the TruClaw app, or tap the link on your iPhone:</p>
          <img src="{qr_url}" width="300" height="300" style="border:1px solid #ddd;padding:8px"/><br><br>
          <a href="{pairing_link}" style="font-size:18px;display:block;margin:16px 0">
            Open in TruClaw ↗
          </a>
          <details style="margin-top:24px;text-align:left">
            <summary style="cursor:pointer;color:#888">Session details</summary>
            <code style="font-size:11px;word-break:break-all;display:block;margin-top:8px">
              userId: {userId}<br>
              sessionId: {session_id}<br>
              pairingLink: {pairing_link}
            </code>
          </details>
          <p style="margin-top:32px">
            <a href="/pair/status" style="color:#888;font-size:13px">View pairing status →</a>
          </p>
        </body>
        </html>
        """

    @app.get("/pair/status", response_class=HTMLResponse)
    async def pair_status(request: Request):
        try:
            devices = load_paired_devices()
        except Exception as e:
            return HTMLResponse(
                content=f"<h2>Error loading pairing state: {e}</h2>",
                status_code=500
            )

        if not devices:
            return f"""
            <html>
            <head>
              <meta name="viewport" content="width=device-width, initial-scale=1">
              <title>TruClaw Pairing Status</title>
            </head>
            <body style="font-family:sans-serif;text-align:center;padding:40px;max-width:500px;margin:0 auto">
              <h2>📱 TruClaw Pairing Status</h2>
              <p style="color:#e55;font-size:18px">⚠️ No device paired</p>
              <p>Challenges cannot be sent until a device is paired.</p>
              <a href="/pair" style="display:inline-block;margin-top:16px;padding:12px 24px;background:#000;color:#fff;border-radius:8px;text-decoration:none">
                Pair a device →
              </a>
            </body>
            </html>
            """

        rows = ""
        for composite_key, device in devices.items():
            user_id = device.get("userId", composite_key.split(":")[0])
            platform = device.get("platform", "unknown")
            paired_at = device.get("pairedAt", "unknown")
            device_hash = composite_key.split(":")[-1] if ":" in composite_key else composite_key[:16]
            icon = "🍎" if platform == "ios" else "🤖" if platform == "android" else "📱"
            rows += f"""
            <tr>
              <td style="padding:12px;border-bottom:1px solid #eee">{user_id}</td>
              <td style="padding:12px;border-bottom:1px solid #eee">{icon} {platform}</td>
              <td style="padding:12px;border-bottom:1px solid #eee;font-family:monospace;font-size:12px">{device_hash}</td>
              <td style="padding:12px;border-bottom:1px solid #eee;font-size:13px">{paired_at}</td>
            </tr>
            """

        count = len(devices)

        return f"""
        <html>
        <head>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>TruClaw Pairing Status</title>
        </head>
        <body style="font-family:sans-serif;padding:40px;max-width:700px;margin:0 auto">
          <h2>📱 TruClaw Pairing Status</h2>
          <p style="color:#2a2;font-size:18px">✅ {count} device{"s" if count != 1 else ""} paired</p>
          <table style="width:100%;border-collapse:collapse;margin-top:16px">
            <thead>
              <tr style="background:#f5f5f5">
                <th style="padding:12px;text-align:left">User</th>
                <th style="padding:12px;text-align:left">Platform</th>
                <th style="padding:12px;text-align:left">Device ID</th>
                <th style="padding:12px;text-align:left">Paired At</th>
              </tr>
            </thead>
            <tbody>
              {rows}
            </tbody>
          </table>
          <div style="margin-top:32px">
            <a href="/pair" style="display:inline-block;padding:10px 20px;background:#000;color:#fff;border-radius:8px;text-decoration:none;font-size:14px">
              Pair another device →
            </a>
          </div>
        </body>
        </html>
        """

    log("[pair_route] /pair and /pair/status routes registered")
