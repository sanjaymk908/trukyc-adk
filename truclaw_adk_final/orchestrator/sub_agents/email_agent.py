import os, json, subprocess
from dotenv import load_dotenv
from google.adk.agents import LlmAgent

print("[OPENCLAW] sample email_agent loaded")
load_dotenv()
MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")

async def send_email(to: str, subject: str, body: str) -> dict:
    print("[OPENCLAW] sample send_email via PortEden")
    cmd = ["porteden", "email", "send", "--to", to, "--subject", subject, "--body", body, "--body-type", "text", "-jc"]
    result = subprocess.run(cmd, env=os.environ.copy(), text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return {"status":"error", "returncode":result.returncode, "stdout":result.stdout, "stderr":result.stderr}
    try: parsed = json.loads(result.stdout)
    except Exception: parsed = result.stdout
    return {"status":"ok", "result": parsed}

email_agent = LlmAgent(model=MODEL, name="email_agent", description="Handles email via PortEden/Gmail only.", instruction="Confirm recipient, subject, and body before sending. Do not trade or browse.", tools=[send_email])
