"""Train the phishing URL classifier on REAL data.

Usage:  python scripts/train_phishing.py
Input:  data/real/phishing.jsonl  (scripts/download_data.py: OpenPhish live
        phishing URLs + Tranco/Majestic top-domain benign URLs)
        Falls back to data/train/phishing.jsonl (synthetic) if missing.
Output: models/phishing.joblib, models/phishing_eval.json

Honest caveat: benign examples are top-domain homepages ("easy negatives").
Real-world phishing also lives on compromised-but-legit-looking domains, so
treat held-out metrics as optimistic; the red-team loop + URL heuristics cover
part of that gap.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.detection.phishing import url_features  # noqa: E402


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
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (auc, classification_report, f1_score,
                                 precision_recall_curve, roc_auc_score)
    from sklearn.model_selection import train_test_split

    real_path = config.DATA_DIR / "real" / "phishing.jsonl"
    synth_path = config.DATA_DIR / "train" / "phishing.jsonl"
    if real_path.exists():
        data_kind = "real (openphish + tranco/majestic)"
        rows = load_jsonl(real_path)
    elif synth_path.exists():
        data_kind = "synthetic (fallback — run scripts/download_data.py)"
        rows = load_jsonl(synth_path)
    else:
        sys.exit("No training data. Run scripts/download_data.py first.")

    texts_key = "url" if "url" in rows[0] else "text"
    urls = [r[texts_key] for r in rows]
    labels = [r["label"] for r in rows]
    by_source = Counter(r.get("source", "unknown") for r in rows)
    print(f"training data: {data_kind}")
    print(f"rows: {len(urls)}  |  labels: {dict(Counter(labels))}")
    for src, n in by_source.most_common():
        print(f"  {src}: {n}")

    feature_names = list(url_features("https://example.com").keys())
    X = np.array([[url_features(u)[k] for k in feature_names] for u in urls])
    y = np.array(labels)

    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.15,
                                              stratify=y, random_state=42)
    clf = LogisticRegression(max_iter=2000, class_weight="balanced")
    clf.fit(X_tr, y_tr)
    proba = clf.predict_proba(X_te)
    pred = clf.predict(X_te)
    phish_idx = list(clf.classes_).index("phishing")
    scores = proba[:, phish_idx]
    y_true_ph = [1 if v == "phishing" else 0 for v in y_te]

    prec, rec, thr = precision_recall_curve(y_true_ph, scores)
    pr_auc = auc(rec, prec)
    roc = roc_auc_score(y_true_ph, scores)
    print(classification_report(y_te, pred, digits=3))
    print(f"macro F1: {f1_score(y_te, pred, average='macro'):.3f}  "
          f"ROC-AUC: {roc:.3f}  PR-AUC(phishing): {pr_auc:.3f}")

    clf.fit(X, y)
    clf.feature_names_ = feature_names
    config.MODELS_DIR.mkdir(exist_ok=True)
    out = config.MODELS_DIR / "phishing.joblib"
    joblib.dump(clf, out)
    print("saved:", out)

    eval_meta = {
        "data_kind": data_kind,
        "n_rows": len(urls),
        "labels": dict(Counter(labels)),
        "by_source": dict(by_source),
        "heldout": {
            "macro_f1": round(float(f1_score(y_te, pred, average="macro")), 4),
            "roc_auc": round(float(roc), 4),
            "pr_auc_phishing": round(float(pr_auc), 4),
            "n_test": len(y_te),
        },
        "caveat": "benign = top-domain homepages (easy negatives); metrics optimistic",
    }
    (config.MODELS_DIR / "phishing_eval.json").write_text(
        json.dumps(eval_meta, indent=2), encoding="utf-8")
    print("metrics saved:", config.MODELS_DIR / "phishing_eval.json")


if __name__ == "__main__":
    main()
