import os
import json
import subprocess
from dotenv import load_dotenv
from google.adk.agents import LlmAgent

print("🔥 LOADED email_agent")

load_dotenv()

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")


async def send_email(to: str, subject: str, body: str) -> dict:
    """Send email using PortEden.

    Args:
        to: Recipient email address, e.g. user@example.com or "John Doe <john@example.com>"
        subject: Email subject
        body: Email body
    """

    print("🔥 email_agent.send_email via PortEden")

    cmd = [
        "porteden",
        "email",
        "send",
        "--to", to,
        "--subject", subject,
        "--body", body,
        "--body-type", "text",
        "-jc",
    ]

    env = os.environ.copy()

    result = subprocess.run(
        cmd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        return {
            "status": "error",
            "command": " ".join(cmd),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    try:
        parsed = json.loads(result.stdout)
    except Exception:
        parsed = result.stdout

    return {
        "status": "ok",
        "result": parsed,
    }


email_agent = LlmAgent(
    model=MODEL,
    name="email_agent",
    description="Handles email through PortEden only.",
    instruction=(
        "You are the email specialist.\n\n"
        "Use send_email for sending email through PortEden.\n"
        "Before sending, confirm recipient, subject, and body.\n\n"
        "Important:\n"
        "- Do not use --send-from.\n"
        "- Rely on PE_API_KEY and optional PE_PROFILE from the environment.\n"
        "- Do not trade.\n"
        "- Do not browse."
    ),
    tools=[send_email],
)
