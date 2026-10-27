"""Train the LLM-router difficulty classifier.

Usage:  python scripts/train_llm_router.py
Input:  data/train/llm_prompts.jsonl {"text", "difficulty": easy|hard}
        Replace seeds with real (prompt, did-small-model-answer-well) pairs
        labeled by an LLM-as-judge for production quality.
Output: models/llm_router.joblib (classes ['easy','hard'])
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.router.llm_router import difficulty_features  # noqa: E402


def main() -> None:
    import joblib
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report
    from sklearn.model_selection import train_test_split

    data_path = config.DATA_DIR / "train" / "llm_prompts.jsonl"
    if not data_path.exists():
        sys.exit("Run scripts/seed_data.py first (or provide data/train/llm_prompts.jsonl)")

    rows = []
    with open(data_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    feature_names = list(difficulty_features("probe").keys())
    X = np.array([[difficulty_features(r["text"])[k] for k in feature_names] for r in rows])
    y = np.array([r["difficulty"] for r in rows])

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y,
                                              random_state=42)
    clf = LogisticRegression(max_iter=1000)
    clf.fit(X_tr, y_tr)
    print(classification_report(y_te, clf.predict(X_te), digits=3))

    clf.fit(X, y)
    clf.feature_names_ = feature_names
    config.MODELS_DIR.mkdir(exist_ok=True)
    out = config.MODELS_DIR / "llm_router.joblib"
    joblib.dump(clf, out)
    print("saved:", out)


if __name__ == "__main__":
    main()
