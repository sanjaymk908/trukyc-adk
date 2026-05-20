import os
import sys
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

sys.stdout.reconfigure(line_buffering=True)

def _log(msg: str) -> None:
    print(f"[browser_agent] {msg}", flush=True)

_log("module loading...")
load_dotenv()

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")


async def browser_navigate(url: str) -> dict:
    """Navigate to a URL and return page content.
    Args:
        url: The URL to navigate to.
    """
    from playwright.async_api import async_playwright
    _log(f"navigating to {url}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page()
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            title = await page.title()
            text = await page.evaluate("() => document.body.innerText")
            await browser.close()
            return {
                "url": url,
                "title": title,
                "text": text[:8000],
                "truncated": len(text) > 8000,
            }
    except Exception as e:
        _log(f"navigate error: {e}")
        return {"url": url, "error": str(e)}


async def browser_search(query: str) -> dict:
    """Search the web using Google and return results.
    Args:
        query: The search query.
    """
    from playwright.async_api import async_playwright
    _log(f"searching for: {query}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page()
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            await page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            text = await page.evaluate("() => document.body.innerText")
            await browser.close()
            return {
                "query": query,
                "text": text[:8000],
                "truncated": len(text) > 8000,
            }
    except Exception as e:
        _log(f"search error: {e}")
        return {"query": query, "error": str(e)}


async def browser_evaluate(url: str, javascript: str) -> dict:
    """Navigate to a URL and execute JavaScript on the page.
    Args:
        url: The URL to navigate to.
        javascript: JavaScript expression to evaluate on the page.
    """
    from playwright.async_api import async_playwright
    _log(f"evaluating JS on {url}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            page = await browser.new_page()
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            result = await page.evaluate(javascript)
            await browser.close()
            return {"url": url, "result": result}
    except Exception as e:
        _log(f"evaluate error: {e}")
        return {"url": url, "error": str(e)}


browser_agent = LlmAgent(
    model=MODEL,
    name="browser_agent",
    description=(
        "Handles web browsing, URL navigation, web search, and JavaScript "
        "execution on web pages using Playwright."
    ),
    instruction=(
        "You are a web browsing specialist.\n\n"
        "You have three tools:\n"
        "- browser_navigate: navigate to a URL and read its content\n"
        "- browser_search: search Google for a query\n"
        "- browser_evaluate: navigate to a URL and run JavaScript on it\n\n"
        "Always use the exact tool names above. Do not invent tool names.\n\n"
        "For read-only research: use browser_navigate or browser_search.\n"
        "For actions on a page (clicks, form submissions, API calls): "
        "use browser_evaluate with appropriate JavaScript.\n\n"
        "Do not trade, send email, or perform non-browsing actions."
    ),
    tools=[
        FunctionTool(browser_navigate),
        FunctionTool(browser_search),
        FunctionTool(browser_evaluate),
    ],
)

_log("browser_agent created")
