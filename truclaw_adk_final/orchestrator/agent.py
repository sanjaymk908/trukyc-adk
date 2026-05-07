import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from truclaw_adk import start_pairing
from .sub_agents.trading_agent import trading_agent
from .sub_agents.research_agent import research_agent
from .sub_agents.email_agent import email_agent

print("[OPENCLAW] TruClaw sample orchestrator loaded")
load_dotenv()
MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")

async def pair_phone() -> dict:
    """Start TruClaw mobile phone pairing and return a QR/link."""
    return await start_pairing()

root_agent = LlmAgent(
    model=MODEL,
    name="orchestrator",
    description="Coordinates and routes tasks to specialist agents.",
    instruction=(
        "You are an orchestrator. Delegate to specialist agents. "
        "Use trading_agent for trades/positions, research_agent for web research, "
        "email_agent for email. Use pair_phone only when user asks to pair TruClaw."
    ),
    tools=[pair_phone],
    sub_agents=[trading_agent, research_agent, email_agent],
)
