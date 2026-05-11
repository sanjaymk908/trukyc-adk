import os
import httpx
from dotenv import load_dotenv
from google.adk.agents import LlmAgent

load_dotenv()
MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")


async def search_hackernews(query: str, hits_per_page: int = 10) -> dict:
    """Search Hacker News for recent posts."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://hn.algolia.com/api/v1/search_by_date",
            params={"query": query, "tags": "story", "hitsPerPage": hits_per_page},
        )
        resp.raise_for_status()

    hits = []
    for item in resp.json().get("hits", []):
        object_id = item.get("objectID")
        hits.append({
            "source": "hackernews",
            "title": item.get("title"),
            "url": item.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
            "hnUrl": f"https://news.ycombinator.com/item?id={object_id}",
            "points": item.get("points"),
            "comments": item.get("num_comments"),
            "createdAt": item.get("created_at"),
        })

    return {"query": query, "results": hits}


hn_agent = LlmAgent(
    model=MODEL,
    name="hn_agent",
    description="Searches Hacker News for current startup/security/agentic AI topics.",
    instruction=(
        "Search Hacker News for fresh, relevant posts. "
        "Prioritize agentic AI security, MCP, prompt injection, startup funding, "
        "agentic commerce, TruClaw-adjacent opportunities, and founder-relevant discussions."
    ),
    tools=[search_hackernews],
)
