import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent

from .sub_agents.trading_agent import trading_agent
from .sub_agents.research_agent import research_agent
from .sub_agents.email_agent import email_agent

print("🔥 LOADED orchestrator root agent")

load_dotenv()

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")

root_agent = LlmAgent(
    model=MODEL,
    name="orchestrator",
    description="Coordinates and routes tasks to specialist agents.",
    instruction=(
        "You are an orchestrator.\n\n"
        "You NEVER perform tasks directly. You ONLY delegate.\n\n"
        "Agents:\n"
        "- trading_agent → trades, positions, portfolio, buy, sell\n"
        "- research_agent → browsing, websites, research\n"
        "- email_agent → email, Gmail, PortEden\n\n"
        "Routing rules:\n"
        "- Positions / holdings / portfolio → trading_agent\n"
        "- Buy / sell → trading_agent\n"
        "- Websites / browsing / research → research_agent\n"
        "- Email / send message → email_agent\n\n"
        "If unclear, ask a clarification question."
    ),
    sub_agents=[
        trading_agent,
        research_agent,
        email_agent,
    ],
)
