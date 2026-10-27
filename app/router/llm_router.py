"""LLM Router: easy prompts -> local quantized model, hard -> big API model.

Difficulty score from cheap features (length, reasoning cues, code, math,
multi-step language). Threshold is configurable; escalation happens when the
local model fails or returns nothing. Feature-based logistic model from
scripts/train_llm_router.py (models/llm_router.joblib) overrides the
heuristic when present.
"""
from __future__ import annotations

import re

from .. import config
from ..schemas import InputPayload

REASONING_CUES = re.compile(
    r"\b(step by step|reason|prove|derive|analyz|compare|evaluate|trade-?off|"
    r"architecture|design|optimize|why|explain in detail|debug|root cause)\b", re.IGNORECASE)
CODE_CUES = re.compile(r"```|\bdef \b|\bclass \b|function|algorithm|regex|SQL|API endpoint", re.IGNORECASE)
MATH_CUES = re.compile(r"\b(calculate|solve|equation|integral|probability|derivative|"
                       r"\d+\s*[\+\-\*/\^]\s*\d+)\b", re.IGNORECASE)
EASY_CUES = re.compile(
    r"\b(hi|hello|hey|thanks|thank you|ok|okay|summarize this sentence|"
    r"rephrase|translate this|fix this typo|what does .* mean)\b", re.IGNORECASE)


def difficulty_features(text: str) -> dict[str, float]:
    return {
        "log_len": min(len(text), 4000) / 1000.0,
        "reasoning_cues": min(len(REASONING_CUES.findall(text)), 3) / 3.0,
        "code_cues": min(len(CODE_CUES.findall(text)), 3) / 3.0,
        "math_cues": min(len(MATH_CUES.findall(text)), 3) / 3.0,
        "easy_cues": min(len(EASY_CUES.findall(text)), 2) / 2.0,
        "n_questions": min(text.count("?"), 4) / 4.0,
    }


HEURISTIC_WEIGHTS = {
    "log_len": 0.45, "reasoning_cues": 1.4, "code_cues": 1.0,
    "math_cues": 0.9, "easy_cues": -1.2, "n_questions": 0.3,
}


def estimate_difficulty(text: str) -> tuple[float, str]:
    """Returns (difficulty 0..1, source)."""
    feats = difficulty_features(text)
    try:
        import joblib
        p = config.MODELS_DIR / "llm_router.joblib"
        if p.exists():
            import numpy as np
            model = joblib.load(p)
            keys = list(model.feature_names_)
            vec = np.array([[feats[k] for k in keys]])
            d = float(model.predict_proba(vec)[0][1])
            return d, "model"
    except Exception:
        pass
    raw = sum(HEURISTIC_WEIGHTS[k] * v for k, v in feats.items())
    d = 1.0 / (1.0 + pow(2.71828, -raw))
    return d, "heuristic"


def route_llm(payload: InputPayload, force_tier: str | None = None) -> dict:
    """Returns {tier, model, difficulty, source, reason}."""
    if force_tier in ("local", "big"):
        model = config.LOCAL_MODEL if force_tier == "local" else config.BIG_MODEL
        return {"tier": force_tier, "model": model, "difficulty": None,
                "source": "forced", "reason": "caller forced tier"}
    difficulty, source = estimate_difficulty(payload.text or "")
    if difficulty >= 0.5:
        return {"tier": "big", "model": config.BIG_MODEL, "difficulty": round(difficulty, 3),
                "source": source, "reason": "difficulty above 0.5 threshold"}
    return {"tier": "local", "model": config.LOCAL_MODEL, "difficulty": round(difficulty, 3),
            "source": source, "reason": "difficulty below 0.5 threshold"}
