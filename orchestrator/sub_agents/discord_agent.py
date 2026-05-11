import os

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StdioConnectionParams,
)
from mcp import StdioServerParameters

print("🔥 LOADED discord_agent")

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

discord_agent = LlmAgent(
    model=MODEL,
    name="discord_agent",
    description="Researches Discord/community discussions and trend signals.",
    instruction=(
        "You are the Discord/community trend scout.\n\n"
        "Use browser tools to inspect public Discord invite pages, "
        "community sites, GitHub discussions, forums, and public community chatter.\n\n"
        "Focus heavily on:\n"
        "- AI agents\n"
        "- MCP ecosystems\n"
        "- prompt injection\n"
        "- AI security incidents\n"
        "- OpenClaw\n"
        "- TruClaw\n"
        "- hackathons\n"
        "- startup opportunities\n"
        "- developer/security communities\n\n"
        "If private Discord content is inaccessible, use public mirrors/proxies/sources."
    ),
    tools=[
        browser_toolset,
    ],
)
