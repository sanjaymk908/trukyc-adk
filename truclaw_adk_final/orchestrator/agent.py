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
    description=(
        "Routes requests to specialist agents. "
        "The orchestrator has no domain tools and must only delegate."
    ),
    instruction=(
        "You are the orchestrator.\n\n"
        "You have exactly one job: delegate the user's request to the correct sub-agent.\n"
        "You must not perform specialist work yourself.\n"
        "You must not call or invent domain tools directly.\n\n"
        "The only action you should take is transferring to one of these agents:\n"
        "- research_agent: websites, URLs, browsing, online research, reading web pages.\n"
        "- trading_agent: trades, positions, holdings, portfolio, buy, sell, market orders.\n"
        "- email_agent: email, Gmail, PortEden, send, draft, reply, forward messages.\n\n"
        "Critical routing rules:\n"
        "- If the user says navigate, open, browse, visit, read a site, or gives a URL, "
        "transfer to research_agent.\n"
        "- If the user asks for positions, holdings, portfolio, current trades, open trades, "
        "buy, or sell, transfer to trading_agent.\n"
        "- If the user asks to send, draft, reply, forward, or manage email, transfer to email_agent.\n\n"
        "Do not invent tool names such as navigate_to_website, browser_open, browser_snapshot, "
        "send_email, place_trade, or fetch_positions at the orchestrator level.\n"
        "Those tools, if available, belong only to specialist agents after transfer.\n\n"
        "If a request needs multiple specialists, transfer in sequence. "
        "Example: research_agent first for web research, then email_agent for drafting/sending."
    ),
    sub_agents=[
        research_agent,
        trading_agent,
        email_agent,
    ],
)
