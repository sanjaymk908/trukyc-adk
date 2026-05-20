import os
from pathlib import Path

RELAY_URL = os.getenv("TRUKYC_RELAY_URL", "").rstrip("/")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_CLASSIFIER_MODEL = os.getenv("TRUCLAW_CLASSIFIER_MODEL", "gemini-3.5-flash")
STATE_DIR = Path(os.getenv("TRUCLAW_STATE_DIR", "./.truclaw"))
PAIRING_DEEPLINK_BASE = os.getenv("TRUCLAW_PAIRING_DEEPLINK_BASE", "https://aasa.trusources.ai/openclaw")
PAIR_POLL_TIMEOUT_SECONDS = int(os.getenv("TRUCLAW_PAIR_POLL_TIMEOUT_SECONDS", "300"))
CHALLENGE_TIMEOUT_SECONDS = int(os.getenv("TRUCLAW_CHALLENGE_TIMEOUT_SECONDS", "120"))
ENFORCE = os.getenv("TRUCLAW_ENFORCE", "1") not in {"0", "false", "False", "no"}
