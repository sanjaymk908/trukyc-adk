import os
import glob
import subprocess
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

# ── environment diagnostics ───────────────────────────────────────────────────

_log(f"PATH: {os.environ.get('PATH')}")
_log(f"PLAYWRIGHT_BROWSERS_PATH: {os.environ.get('PLAYWRIGHT_BROWSERS_PATH', 'not set')}")

try:
    npx_which = subprocess.check_output(["which", "npx"], text=True).strip()
    _log(f"which npx: {npx_which}")
except Exception as e:
    _log(f"which npx failed: {e}")

try:
    node_version = subprocess.check_output(["node", "--version"], text=True).strip()
    _log(f"node version: {node_version}")
except Exception as e:
    _log(f"node --version failed: {e}")

# ── chromium discovery ────────────────────────────────────────────────────────

def _chromium_executable() -> str:
    patterns = [
        "/ms-playwright/chromium-*/chrome-linux64/chrome",
        "/ms-playwright/chromium-*/chrome-linux/chrome",
        "/ms-playwright/chromium_headless_shell-*/chrome-linux64/headless_shell",
        "/ms-playwright/chromium_headless_shell-*/chrome-linux/headless_shell",
        "/root/.cache/ms-playwright/chromium-*/chrome-linux64/chrome",
        "/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
    ]
    for pattern in patterns:
        matches = glob.glob(pattern)
        _log(f"chromium glob '{pattern}': {matches}")
        if matches:
            _log(f"chromium resolved: {matches[0]}")
            return matches[0]
    _log("chromium not found in any known path")
    return ""


# list /ms-playwright contents
try:
    ms_pw_contents = os.listdir("/ms-playwright")
    _log(f"/ms-playwright contents: {ms_pw_contents}")
except Exception as e:
    _log(f"/ms-playwright listing failed: {e}")

CHROMIUM_PATH = _chromium_executable()
_log(f"final chromium path: '{CHROMIUM_PATH}'")

# ── verify chromium is executable ────────────────────────────────────────────

if CHROMIUM_PATH:
    try:
        result = subprocess.run(
            [CHROMIUM_PATH, "--version"],
            capture_output=True, text=True, timeout=5
        )
        _log(f"chromium --version stdout: {result.stdout.strip()}")
        _log(f"chromium --version stderr: {result.stderr.strip()[:200]}")
    except Exception as e:
        _log(f"chromium --version failed: {e}")

# ── build MCP args ────────────────────────────────────────────────────────────

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

# ── toolset ───────────────────────────────────────────────────────────────────

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

# ── agent ─────────────────────────────────────────────────────────────────────

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
