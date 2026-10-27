"""Central configuration, read from environment with sane defaults."""
import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.getenv("AI_ROUTER_DATA_DIR", APP_ROOT / "data"))
MODELS_DIR = Path(os.getenv("AI_ROUTER_MODELS_DIR", APP_ROOT / "models"))
POLICY_DIR = Path(__file__).resolve().parent / "policy" / "policies"
TENANTS_FILE = Path(__file__).resolve().parent / "policy" / "tenants.yaml"
DASHBOARD_TEMPLATE = Path(__file__).resolve().parent / "dashboard" / "templates" / "index.html"

AUDIT_DB_PATH = DATA_DIR / "audit.db"
HARD_EXAMPLES_PATH = DATA_DIR / "hard_examples.jsonl"
REDTEAM_HISTORY_PATH = DATA_DIR / "redteam_history.jsonl"
LEARNED_PATTERNS_PATH = DATA_DIR / "learned_patterns.json"
BANDIT_STATE_PATH = DATA_DIR / "bandit_state.npz"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "gemma3:4b")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
BIG_MODEL = os.getenv("BIG_MODEL", "gpt-4o-mini")

COST_BIG_PER_1K = float(os.getenv("COST_BIG_PER_1K", "0.15"))
COST_LOCAL_PER_1K = float(os.getenv("COST_LOCAL_PER_1K", "0.0"))
AVG_RESPONSE_TOKENS = 400  # rough estimate for cost-saved math

DEFAULT_RATE_LIMIT_PER_MIN = int(os.getenv("DEFAULT_RATE_LIMIT_PER_MIN", "120"))

BANDIT_ALPHA = float(os.getenv("BANDIT_ALPHA", "0.3"))
BANDIT_COST_WEIGHT = float(os.getenv("BANDIT_COST_WEIGHT", "0.1"))
BANDIT_LATENCY_WEIGHT = float(os.getenv("BANDIT_LATENCY_WEIGHT", "0.05"))


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
