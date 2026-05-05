import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

print("🔥 LOADED research_agent")

load_dotenv()

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")

browser_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=["-y", "@playwright/mcp@latest"],
        )
    ),
)

research_agent = LlmAgent(
    model=MODEL,
    name="research_agent",
    description="Handles browsing and web research.",
    instruction=(
        "Use browser tools for all web tasks.\n"
        "Do not trade. Do not send email."
    ),
    tools=[browser_toolset],
)
