import os
import glob
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StdioConnectionParams,
)
from mcp import StdioServerParameters

try:
    from truclaw_adk.logging_utils import log
except Exception:
    def log(msg: str) -> None:
        print(msg, flush=True)


log("[OPENCLAW] research_agent module loaded")

load_dotenv()

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")


def _chromium_executable() -> str:
    patterns = [
        "/ms-playwright/chromium-*/chrome-linux/chrome",
        "/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
        "/home/*/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]

    for pattern in patterns:
        matches = glob.glob(pattern)
        log(f"[research_agent] chromium glob {pattern}: {matches}")
        if matches:
            return matches[0]

    return ""


def _mcp_command() -> str:
    candidates = [
        os.getenv("PLAYWRIGHT_MCP_COMMAND", ""),
        "/usr/local/bin/mcp-server-playwright",
        "/usr/bin/mcp-server-playwright",
        "mcp-server-playwright",
    ]

    for candidate in candidates:
        if candidate:
            return candidate

    return "mcp-server-playwright"


CHROMIUM_PATH = _chromium_executable()
MCP_COMMAND = _mcp_command()

MCP_ARGS = [
    "--browser",
    "chromium",
    "--headless",
    "--no-sandbox",
]

if CHROMIUM_PATH:
    MCP_ARGS.extend(["--executable-path", CHROMIUM_PATH])

MCP_ENV = {
    **os.environ,
    "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright",
    "PATH": (
        "/usr/local/sbin:/usr/local/bin:"
        "/usr/sbin:/usr/bin:/sbin:/bin"
    ),
}

log(f"[research_agent] model: {MODEL}")
log(f"[research_agent] chromium path: {CHROMIUM_PATH}")
log(f"[research_agent] MCP command: {MCP_COMMAND}")
log(f"[research_agent] MCP args: {MCP_ARGS}")
log(f"[research_agent] PATH: {MCP_ENV.get('PATH')}")


browser_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=MCP_COMMAND,
            args=MCP_ARGS,
            env=MCP_ENV,
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
        "Use the available Playwright tools exactly as exposed by the runtime. "
        "Do not assume tool names beyond what the runtime provides.\n\n"
        "Typical workflow:\n"
        "1. Navigate to a page.\n"
        "2. Read page content using snapshot/text tools.\n"
        "3. Return concise findings with relevant source context.\n\n"
        "Do not trade, send email, purchase items, submit forms, "
        "or modify external systems."
    ),
    tools=[browser_toolset],
)

root_agent = research_agent
