import os

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StdioConnectionParams,
)
from mcp import StdioServerParameters

print("🔥 LOADED x_agent")

load_dotenv()

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")

browser_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="/opt/homebrew/bin/npx",
            args=["-y", "@playwright/mcp@latest"],
        )
    ),
)

x_agent = LlmAgent(
    model=MODEL,
    name="x_agent",
    description="Researches Twitter/X trends and discussions.",
    instruction=(
        "You are the Twitter/X trend scout.\n\n"
        "Use browser tools to inspect public Twitter/X pages, search pages, "
        "profiles, discussions, funding chatter, security incidents, and startup conversations.\n\n"
        "Focus heavily on:\n"
        "- AI agents\n"
        "- MCP security\n"
        "- prompt injection\n"
        "- OpenClaw\n"
        "- TruClaw\n"
        "- agentic commerce\n"
        "- startup funding\n"
        "- hackathons\n"
        "- enterprise AI security\n\n"
        "Return concise, high-signal findings with URLs and why they matter."
    ),
    tools=[
        browser_toolset,
    ],
)
