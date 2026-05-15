import os
import sys
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

sys.stdout.reconfigure(line_buffering=True)


def _log(msg: str) -> None:
    print(f"[research_agent] {msg}", flush=True)


_log("module loading...")
load_dotenv()

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")
_log(f"model: {MODEL}")

MCP_ARGS = [
    "-y", "@playwright/mcp@latest",
    "--browser", "chromium",
    "--no-sandbox",
]

MCP_ENV = {
    **os.environ,
    "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright",
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
}

_log(f"MCP command: /usr/bin/npx")
_log(f"MCP args: {MCP_ARGS}")
_log(f"PLAYWRIGHT_BROWSERS_PATH: {MCP_ENV['PLAYWRIGHT_BROWSERS_PATH']}")

browser_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="/usr/bin/npx",
            args=MCP_ARGS,
            env=MCP_ENV,
        )
    )
)

_log("McpToolset created")

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
    tools=[browser_toolset],
)

_log("research_agent created")
