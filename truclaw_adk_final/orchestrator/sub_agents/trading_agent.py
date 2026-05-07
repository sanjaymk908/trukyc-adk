import os, httpx
from dotenv import load_dotenv
from google.adk.agents import LlmAgent

print("[OPENCLAW] sample trading_agent loaded")
load_dotenv()
MODEL = os.getenv("ADK_MODEL", "gemini-2.5-flash")
API_TRADE_URL = os.getenv("API_TRADE_URL", "https://simul8or.com/api/v1/agent/AgentTrade.ashx")
API_POSITIONS_URL = os.getenv("API_POSITIONS_URL", "https://simul8or.com/api/v1/agent/AgentTrades.ashx")
SIMUL8OR_API_KEY = os.environ.get("SIMUL8OR_API_KEY", "")

def _parse(resp):
    try: return resp.json()
    except Exception: return resp.text

async def place_trade(symbol: str, side: str, price: float) -> dict:
    print("[OPENCLAW] sample place_trade POST AgentTrade")
    side = side.lower().strip(); symbol = symbol.upper().strip()
    if side not in {"buy", "sell"}: raise ValueError("Only buy/sell allowed")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(API_TRADE_URL, headers={"X-Simul8or-Key": SIMUL8OR_API_KEY, "Content-Type":"application/json"}, json={"symbol":symbol,"side":side,"price":price})
        resp.raise_for_status()
    return {"status":"ok", "result": _parse(resp)}

async def fetch_positions() -> dict:
    print("[OPENCLAW] sample fetch_positions GET AgentTrades")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(API_POSITIONS_URL, headers={"X-Simul8or-Key": SIMUL8OR_API_KEY, "Content-Type":"application/json"})
        resp.raise_for_status()
    return {"status":"ok", "result": _parse(resp)}

trading_agent = LlmAgent(
    model=MODEL,
    name="trading_agent",
    description="Handles Simul8or trades and positions only.",
    instruction="Use fetch_positions for positions/portfolio. Use place_trade only for buy/sell trades.",
    tools=[fetch_positions, place_trade],
)
