import os
import glob
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

print("[OPENCLAW] sample research_agent loaded")
load_dotenv()

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")


def _chromium_executable() -> str:
    matches = glob.glob("/ms-playwright/chromium-*/chrome-linux/chrome")
    return matches[0] if matches else ""


_chromium = _chromium_executable()

browser_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="/usr/bin/npx",
            args=[
                "-y", "@playwright/mcp@latest",
                "--no-sandbox",
                *( ["--executable-path", _chromium] if _chromium else [] ),
            ],
            env={
                **os.environ,
                "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright",
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            }
        )
    )
)

research_agent = LlmAgent(
    model=MODEL,
    name="research_agent",
    description="Handles web research and browsing with Playwright MCP.",
    instruction=(
        "You are a web research specialist.\n\n"
        "You have Playwright browser tools available. "
        "Always introspect your available tools before acting — "
        "do not assume tool names. Use exactly the tool names you have.\n\n"
        "Typical flow for a URL request:\n"
        "1. Navigate to the URL using your navigate tool\n"
        "2. Read the page content using your snapshot or text tool\n"
        "3. Return the relevant information\n\n"
        "Do not trade, send email, or perform any non-research actions."
    ),
    tools=[browser_toolset]
)
