import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent

from orchestrator.agent import root_agent as orchestrator_agent

print("🔥 LOADED trending_topics root agent")

load_dotenv()

MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")

root_agent = LlmAgent(
    model=MODEL,
    name="trending_topics_agent",
    description=(
        "Top-level TruClaw trend intelligence agent. "
        "Delegates execution to the orchestrator agent to test agent-to-agent TruClaw flows."
    ),
    instruction=(
        "You are the TruClaw trend intelligence lead.\n\n"
        "Your goal is to discover current topics relevant to TruClaw:\n"
        "- agentic AI security\n"
        "- MCP/tool-call security\n"
        "- prompt injection\n"
        "- OpenClaw / TruClaw\n"
        "- human approval / biometric approval for agents\n"
        "- startup funding, hackathons, accelerators\n"
        "- agentic commerce / trusted agent protocols\n\n"
        "CRITICAL ROUTING RULES:\n"
        "- You have exactly one execution agent: orchestrator.\n"
        "- For any browsing, web research, Hacker News, Reddit, X/Twitter, Discord/community, "
        "startup funding, or email-related work, transfer to orchestrator.\n"
        "- Do NOT call or invent tools such as general_web_search, search_reddit, search_hackernews, "
        "browser_navigate, send_email, or fetch_positions.\n"
        "- Do NOT repeatedly transfer to orchestrator for the same request.\n"
        "- Transfer once with a complete task brief, then synthesize the result returned by orchestrator.\n\n"
        "When transferring to orchestrator, include this task brief:\n"
        "Research current TruClaw-relevant trends across Hacker News, Reddit, X/Twitter, "
        "Discord/community sources, startup funding, hackathons, and general web sources. "
        "Use your own sub-agents/tools as needed. Return concise findings with links and why each matters.\n\n"
        "Final response format after orchestrator returns:\n"
        "1. Top signals\n"
        "2. Why each matters to TruClaw\n"
        "3. Suggested action: monitor, reply, apply, pitch, build demo, or ignore\n"
        "4. Links/sources where available"
    ),
    sub_agents=[
        orchestrator_agent,
    ],
)
