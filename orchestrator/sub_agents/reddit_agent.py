import os
import httpx
from dotenv import load_dotenv
from google.adk.agents import LlmAgent

load_dotenv()
MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")


async def search_reddit(query: str, limit: int = 10) -> dict:
    """Search Reddit public JSON for recent posts."""
    async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "TruClawADK/0.1"}) as client:
        resp = await client.get(
            "https://www.reddit.com/search.json",
            params={"q": query, "sort": "new", "limit": limit},
        )
        resp.raise_for_status()

    results = []
    for child in resp.json().get("data", {}).get("children", []):
        post = child.get("data", {})
        results.append({
            "source": "reddit",
            "title": post.get("title"),
            "subreddit": post.get("subreddit_name_prefixed"),
            "url": f"https://www.reddit.com{post.get('permalink')}",
            "score": post.get("score"),
            "comments": post.get("num_comments"),
            "createdUtc": post.get("created_utc"),
        })

    return {"query": query, "results": results}


reddit_agent = LlmAgent(
    model=MODEL,
    name="reddit_agent",
    description="Searches Reddit for current TruClaw-relevant discussions.",
    instruction=(
        "Search Reddit for current discussion signals. "
        "Prioritize AI agents, AI security, cybersecurity, startups, funding, hackathons, "
        "MCP, prompt injection, agentic commerce, and human approval workflows."
    ),
    tools=[search_reddit],
)
