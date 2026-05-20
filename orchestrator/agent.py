import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext
from .sub_agents.trading_agent import trading_agent
from .sub_agents.research_agent import research_agent
from .sub_agents.email_agent import email_agent
from .sub_agents.hn_agent import hn_agent
from .sub_agents.reddit_agent import reddit_agent
from .sub_agents.x_agent import x_agent
from .sub_agents.discord_agent import discord_agent
from .sub_agents.browser_agent import browser_agent

print("🔥 LOADED orchestrator root agent")
load_dotenv()

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")


def _resolve_user_id(tool_context: ToolContext) -> str:
    try:
        for attr in ("_invocation_context", "invocation_context"):
            ctx = getattr(tool_context, attr, None)
            if ctx is not None and hasattr(ctx, "user_id"):
                return ctx.user_id
    except Exception:
        pass
    return "default"


async def truclaw_pair(tool_context: ToolContext) -> dict:
    """Pair a TruClaw mobile device for biometric authorization. Call this when the user asks to pair their phone or TruClaw device."""
    from truclaw_adk.pairing import start_pairing
    user_id = _resolve_user_id(tool_context)
    result = await start_pairing(user_id=user_id, start_background_poll=True)
    if result.get("status") == "error":
        return {"error": result.get("reason")}
    return {
        "message": (
            f"Open this link on your iPhone to pair with TruClaw:\n"
            f"{result['pairingLink']}\n\n"
            f"Or scan the QR code at:\n"
            f"{result['qrImageUrl']}"
        ),
        "pairingLink": result["pairingLink"],
        "qrImageUrl": result["qrImageUrl"],
        "sessionId": result["sessionId"],
        "userId": user_id,
    }


async def truclaw_status(tool_context: ToolContext) -> dict:
    """Check TruClaw pairing status for the current user. Call this when the user asks about their TruClaw pairing status or if their device is paired."""
    from truclaw_adk.pairing import find_paired_devices_for_user
    user_id = _resolve_user_id(tool_context)
    devices = find_paired_devices_for_user(user_id)
    if not devices:
        return {
            "paired": False,
            "userId": user_id,
            "message": (
                f"No device paired for userId={user_id}. "
                f"Ask me to pair your TruClaw device."
            ),
        }
    return {
        "paired": True,
        "deviceCount": len(devices),
        "userId": user_id,
        "devices": [
            {
                "platform": d.get("platform", "unknown"),
                "pairedAt": d.get("pairedAt", "unknown"),
            }
            for d in devices
        ],
        "message": f"{len(devices)} device(s) paired for userId={user_id}.",
    }


root_agent = LlmAgent(
    model=MODEL,
    name="orchestrator",
    description=(
        "Routes user requests to specialist agents. "
        "The orchestrator has no domain tools and should only delegate, "
        "except for TruClaw device management tools which it handles directly."
    ),
    instruction=(
        "You are the orchestrator.\n\n"
        "You have exactly one job: delegate the user's request to the correct specialist agent.\n"
        "Do not perform specialist work yourself.\n"
        "Do not invent or call domain tools directly.\n\n"
        "TruClaw device management (handle directly, do NOT delegate):\n"
        "- If the user asks to pair their phone, pair their device, or set up TruClaw, "
        "call the truclaw_pair tool directly.\n"
        "- If the user asks about their TruClaw pairing status, whether their device is paired, "
        "or TruClaw status, call the truclaw_status tool directly.\n\n"
        "Available specialist agents:\n"
        "- research_agent: websites, URLs, browsing, online research, reading web pages.\n"
        "- trading_agent: trades, positions, holdings, portfolio, buy, sell, market orders.\n"
        "- email_agent: email, Gmail, PortEden, send, draft, reply, forward messages.\n"
        "- hn_agent: Hacker News searches and HN trend discovery.\n"
        "- reddit_agent: Reddit searches and subreddit trend discovery.\n"
        "- x_agent: Twitter/X public trend discovery using browser-accessible sources.\n"
        "- discord_agent: Discord/community trend discovery using public/browser-accessible sources.\n\n"
        "Routing rules:\n"
        "- If the user says navigate, open, browse, visit, read a site, gives a URL, "
        "or needs JavaScript execution on a page, transfer to browser_agent.\n"
        "- If the user asks for positions, holdings, portfolio, current trades, open trades, "
        "buy, or sell, transfer to trading_agent.\n"
        "- If the user asks to send, draft, reply, forward, or manage email, transfer to email_agent.\n"
        "- If the user asks about Hacker News or HN, transfer to hn_agent.\n"
        "- If the user asks about Reddit or subreddits, transfer to reddit_agent.\n"
        "- If the user asks about Twitter or X, transfer to x_agent.\n"
        "- If the user asks about Discord, communities, forums, or community chatter, "
        "transfer to discord_agent.\n"
        "- If the user asks for trending topics, current topics, market intel, funding opportunities, "
        "hackathons, startup programs, or security events relevant to TruClaw, use the most relevant "
        "source-specific agents: hn_agent, reddit_agent, x_agent, discord_agent, and research_agent.\n\n"
        "TruClaw trend-intelligence focus areas:\n"
        "- agentic AI security\n"
        "- MCP and tool-call security\n"
        "- prompt injection and unsafe delegation\n"
        "- human approval, human presence, biometric approval for agents\n"
        "- OpenClaw ecosystem\n"
        "- agent identity and agentic commerce\n"
        "- Visa/Mastercard trusted-agent commerce\n"
        "- Google Cloud/startup/hackathon/funding opportunities\n\n"
        "Do not invent tool names such as navigate, navigate_to_website, browser_open, "
        "browser_snapshot, send_email, place_trade, fetch_positions, search_reddit, or search_hackernews "
        "at the orchestrator level. Those belong only to specialist agents after transfer.\n\n"
        "If a request needs multiple specialists, transfer in sequence. "
        "Example: use source-specific trend agents first, use research_agent for validation, "
        "then use email_agent only if the user explicitly asks to send/share a report."
    ),
    tools=[
        FunctionTool(truclaw_pair),
        FunctionTool(truclaw_status),
    ],
    sub_agents=[
        browser_agent, 
        research_agent,
        trading_agent,
        email_agent,
        hn_agent,
        reddit_agent,
        x_agent,
        discord_agent,
    ],
)
