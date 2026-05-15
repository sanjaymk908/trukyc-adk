import os
import glob
import asyncio

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import (
    McpToolset,
    StdioConnectionParams,
)
from mcp import StdioServerParameters

print("[OPENCLAW] sample research_agent loaded")

load_dotenv()

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")


# -----------------------------------------------------------------------------
# Chromium discovery
# -----------------------------------------------------------------------------

def _chromium_executable() -> str:
    matches = glob.glob("/ms-playwright/chromium-*/chrome-linux/chrome")
    print(f"[research_agent] chromium glob matches: {matches}")
    return matches[0] if matches else ""


CHROMIUM_PATH = _chromium_executable()

NPX = (
    os.getenv("NPX_PATH")
    or os.popen("which npx").read().strip()
    or "npx"
)

print(f"[research_agent] chromium path: {CHROMIUM_PATH}")
print(f"[research_agent] npx path: {NPX}")
print(f"[research_agent] PATH: {os.environ.get('PATH')}")


# -----------------------------------------------------------------------------
# MCP args
# -----------------------------------------------------------------------------

MCP_ARGS = [
    "-y",
    "@playwright/mcp@latest",
    "--browser",
    "chromium",
    "--no-sandbox",
]

if CHROMIUM_PATH:
    MCP_ARGS.extend([
        "--executable-path",
        CHROMIUM_PATH,
    ])

print(f"[research_agent] MCP args: {MCP_ARGS}")


# -----------------------------------------------------------------------------
# Optional MCP connectivity test
# -----------------------------------------------------------------------------

async def _test_mcp():
    try:
        toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=NPX,
                    args=MCP_ARGS,
                    env={
                        **os.environ,
                        "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright",
                        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                    },
                )
            )
        )

        tools, ctx = await toolset.load_tools()

        print(
            f"[research_agent] MCP tools loaded: "
            f"{[t.name for t in tools]}"
        )

        await ctx.aclose()

    except Exception as e:
        print(
            f"[research_agent] MCP session error: "
            f"{type(e).__name__}: {e}"
        )

        import traceback
        traceback.print_exc()


if os.getenv("DEBUG_MCP") == "1":
    try:
        asyncio.run(_test_mcp())
    except Exception as e:
        print(f"[research_agent] event loop error: {e}")


# -----------------------------------------------------------------------------
# Browser toolset
# -----------------------------------------------------------------------------

browser_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=NPX,
            args=MCP_ARGS,
            env={
                **os.environ,
                "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright",
                "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            },
        )
    )
)


# -----------------------------------------------------------------------------
# Agent
# -----------------------------------------------------------------------------

research_agent = LlmAgent(
    model=MODEL,
    name="research_agent",
    description="Handles web research and browsing with Playwright MCP.",
    instruction=(
        "You are a web research specialist.\n\n"

        "You have Playwright browser tools available. "
        "Always introspect your available tools before acting. "
        "Never assume tool names.\n\n"

        "Typical workflow:\n"
        "1. Navigate to a page\n"
        "2. Read content via snapshot/text tools\n"
        "3. Return concise findings\n\n"

        "Do not perform financial actions, "
        "send emails, or modify external systems."
    ),
    tools=[browser_toolset],
)
