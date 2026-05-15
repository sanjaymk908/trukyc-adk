import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

print("[OPENCLAW] sample research_agent loaded")
load_dotenv()
MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")

browser_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=[
                "-y", "@playwright/mcp@latest",
                "--browser", "chromium",
                "--executable-path", "/usr/bin/chromium",
                "--no-sandbox",
            ]
        )
    )
)
research_agent = LlmAgent(model=MODEL, name="research_agent", description="Handles web research with Playwright MCP.", instruction="Use browser tools for websites. Do not trade or send email.", tools=[browser_toolset])
