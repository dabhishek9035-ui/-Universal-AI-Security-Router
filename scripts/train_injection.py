"""Train the prompt-injection classifier on REAL data.

Usage:  python scripts/train_injection.py
Input:  data/real/injection.jsonl  (from scripts/download_data.py — HuggingFace
        injection datasets + OpenPhish-style real sources + curated benign)
        Falls back to data/train/injection.jsonl (synthetic) if real is missing.
Output: models/injection.joblib   (pipeline, classes ['benign','malicious'])
        models/injection_eval.json (held-out metrics + data provenance)
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def main() -> None:
    import joblib
    import numpy as np
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (auc, classification_report, f1_score,
                                 precision_recall_curve, roc_auc_score)
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import FeatureUnion, Pipeline

    real_path = config.DATA_DIR / "real" / "injection.jsonl"
    synth_path = config.DATA_DIR / "train" / "injection.jsonl"
    if real_path.exists():
        data_kind = "real (huggingface + curated)"
        rows = load_jsonl(real_path)
    elif synth_path.exists():
        data_kind = "synthetic (fallback — run scripts/download_data.py for real data)"
        rows = load_jsonl(synth_path)
    else:
        sys.exit("No training data found. Run scripts/download_data.py first.")

    texts = [r["text"] for r in rows]
    labels = [r["label"] for r in rows]
    by_source = Counter(r.get("source", "unknown") for r in rows)
    print(f"training data: {data_kind}")
    print(f"rows: {len(texts)}  |  labels: {dict(Counter(labels))}")
    for src, n in by_source.most_common():
        print(f"  {src}: {n}")

    X_tr, X_te, y_tr, y_te = train_test_split(
        texts, labels, test_size=0.15, stratify=labels, random_state=42)

    features = FeatureUnion([
        ("word", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True,
                                 max_features=120_000)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3,
                                 sublinear_tf=True, max_features=200_000)),
    ])
    base = LogisticRegression(max_iter=2000, class_weight="balanced", C=4.0)
    pipe = Pipeline([("features", features),
                     ("clf", CalibratedClassifierCV(base, method="sigmoid", cv=3))])

    import time as _time
    t0 = _time.time()
    pipe.fit(X_tr, y_tr)
    print(f"trained in {_time.time() - t0:.1f}s")

    proba = pipe.predict_proba(X_te)
    pred = pipe.predict(X_te)
    mal_idx = list(pipe.classes_).index("malicious")
    scores = proba[:, mal_idx]
    y_true_mal = [1 if y == "malicious" else 0 for y in y_te]

    prec, rec, thr = precision_recall_curve(y_true_mal, scores)
    pr_auc = auc(rec, prec)
    roc = roc_auc_score(y_true_mal, scores)
    print(classification_report(y_te, pred, digits=3))
    print(f"macro F1: {f1_score(y_te, pred, average='macro'):.3f}  "
          f"ROC-AUC: {roc:.3f}  PR-AUC(malicious): {pr_auc:.3f}")

    # threshold sweep — recall achievable at precision-first operating points
    for target in (0.98, 0.95, 0.90):
        i = next((i for i, p in enumerate(prec[:-1]) if p >= target), None)
        if i is not None:
            print(f"  @{target:.0%} precision -> recall {rec[i]:.3f} (threshold {thr[i]:.3f})")

    # retrain on all data for the shipped model
    pipe.fit(texts, labels)
    config.MODELS_DIR.mkdir(exist_ok=True)
    out = config.MODELS_DIR / "injection.joblib"
    joblib.dump(pipe, out)
    print("saved:", out)

    eval_meta = {
        "data_kind": data_kind,
        "n_rows": len(texts),
        "labels": dict(Counter(labels)),
        "by_source": dict(by_source),
        "heldout": {
            "macro_f1": round(float(f1_score(y_te, pred, average="macro")), 4),
            "roc_auc": round(float(roc), 4),
            "pr_auc_malicious": round(float(pr_auc), 4),
            "n_test": len(y_te),
        },
        "trained_at": _time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (config.MODELS_DIR / "injection_eval.json").write_text(
        json.dumps(eval_meta, indent=2), encoding="utf-8")
    print("metrics saved:", config.MODELS_DIR / "injection_eval.json")


if __name__ == "__main__":
    main()
