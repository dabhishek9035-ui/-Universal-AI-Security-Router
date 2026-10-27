"""Log / network anomaly detector.

Log path: template-mining lite (normalize numbers/ids/uuids/IPs into template
tokens), then rare-template z-scoring against a baseline frequency table fit
via fit_baseline(). Network path: z-scores over flow features passed in
payload.meta["flow_features"] (e.g. bytes, packets, duration, ports).
Optional: IsolationForest from scripts/train_anomaly.py (models/anomaly.joblib).
"""
from __future__ import annotations

import math
import re
import threading

from .. import config
from .base import BaseDetector, Detection

_TOKEN_NORMALIZERS = [
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?\b"), "<TS>"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<UUID>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "<IP>"),
    (re.compile(r"\b[0-9a-f]{16,}\b", re.IGNORECASE), "<HEX>"),
    (re.compile(r"\b\d+\b"), "<N>"),
]

def _template(line: str) -> str:
    out = line
    for regex, token in _TOKEN_NORMALIZERS:
        out = regex.sub(token, out)
    return out.strip()[:200]

_baseline: dict[str, float] = {}
_baseline_loaded = False
_baseline_lock = threading.Lock()

DEFAULT_BASELINE: dict[str, float] = {
    # log10 template frequency for very common shapes (cold-start prior)
    "<TS> <N> <N> INFO <N> ms <N>": -1.0,
    "GET /api/<N> <N> <TS>": -1.2,
    "<IP> - - <TS> \"GET / HTTP/1.1\" <N> <N>": -1.2,
}


def fit_baseline(log_lines: list[str]) -> None:
    """Fit template frequency baseline from known-good logs; persisted to data."""
    counts: dict[str, int] = {}
    for line in log_lines:
        t = _template(line)
        counts[t] = counts.get(t, 0) + 1
    import json
    n = max(len(log_lines), 1)
    freq = {t: math.log10(c / n) for t, c in counts.items()}
    with _baseline_lock:
        _baseline.clear()
        _baseline.update(freq)
        try:
            config.ensure_dirs()
            (config.DATA_DIR / "log_baseline.json").write_text(
                json.dumps(freq, indent=2), encoding="utf-8")
        except Exception:
            pass


def _load_baseline() -> dict[str, float]:
    global _baseline_loaded
    with _baseline_lock:
        if not _baseline_loaded:
            _baseline_loaded = True
            try:
                import json
                p = config.DATA_DIR / "log_baseline.json"
                if p.exists():
                    _baseline.update(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
        return _baseline or DEFAULT_BASELINE


class LogAnomalyDetector(BaseDetector):
    name = "log_anomaly"
    input_types = ("log", "traffic")
    cost = 1.0
    latency_ms = 6.0

    def predict(self, payload, input_type: str) -> Detection:
        if input_type == "traffic":
            return self._score_traffic(payload)
        return self._score_logs(payload)

    def _score_traffic(self, payload) -> Detection:
        feats = (payload.meta or {}).get("flow_features") or {}
        if not feats:
            return Detection(detector=self.name, label="benign", score=0.0,
                             explanation="no flow features provided")
        # expected ranges: (mean, std) for common flow stats
        RANGES = {
            "bytes": (2000, 20000), "packets": (20, 500), "duration_s": (1, 120),
            "dst_port": (0, 65535), "bytes_per_packet": (100, 1500),
            "syn_count": (1, 10),
        }
        reasons, worst = [], 0.0
        for key, value in feats.items():
            if key not in RANGES or not isinstance(value, (int, float)):
                continue
            mean, std = RANGES[key]
            z = abs(value - mean) / std
            if z > 3:
                reasons.append(f"{key}={value:g} (z={z:.1f})")
                worst = max(worst, min(1.0, z / 10))
        if (feats.get("syn_count") or 0) > 100:
            reasons.append("possible SYN flood")
            worst = max(worst, 0.9)
        score = min(worst, 1.0)
        return Detection(
            detector=self.name, label="anomaly" if score >= 0.5 else "benign",
            score=score, category="traffic_anomaly" if score >= 0.5 else None,
            explanation="; ".join(reasons) if reasons else "flow stats within expected ranges",
        )

    def _score_logs(self, payload) -> Detection:
        text = payload.text or ""
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            return Detection(detector=self.name, label="benign", score=0.0,
                             explanation="empty log")

        model = None
        try:
            import joblib
            p = config.MODELS_DIR / "anomaly.joblib"
            if p.exists():
                model = joblib.load(p)
        except Exception:
            model = None

        if model is not None:
            try:
                vecs = [self._featurize(ln) for ln in lines[:500]]
                preds = model.score_samples(vecs)  # lower = more anomalous
                worst_idx = min(range(len(preds)), key=lambda i: preds[i])
                score = min(1.0, max(0.0, -preds[worst_idx]))
                return Detection(
                    detector=self.name,
                    label="anomaly" if score >= 0.5 else "benign",
                    score=score,
                    category="log_anomaly" if score >= 0.5 else None,
                    explanation=f"IsolationForest worst line: {lines[worst_idx][:120]}",
                )
            except Exception:
                pass

        baseline = _load_baseline()
        reasons, worst = [], 0.0
        SUSPICIOUS_KW = re.compile(
            r"\b(ERROR|FATAL|CRITICAL|Failed password|authentication failure|sudo|root)\b", re.I)
        OPAQUE_BLOB = re.compile(r"[A-Za-z0-9+/=]{20,}")
        unseen_count = 0
        for line in lines[:200]:
            t = _template(line)
            log10_freq = baseline.get(t)
            if log10_freq is None:
                unseen_count += 1
                line_penalty = 0.35  # unseen alone is weak evidence
            elif log10_freq < -2.0:
                line_penalty = min(0.9, abs(log10_freq) / 3.0)
            else:
                continue
            if SUSPICIOUS_KW.search(line):
                line_penalty += 0.3
            if OPAQUE_BLOB.search(line):
                line_penalty += 0.25
            worst = max(worst, line_penalty)
            reasons.append(f"{'unseen' if log10_freq is None else 'rare'} template: {t[:90]}")

        # many unseen lines at once is itself the anomaly signal
        if len(lines) >= 5 and unseen_count / len(lines) > 0.4:
            worst = max(worst, min(1.0, unseen_count / len(lines)))
            reasons.append(f"{unseen_count}/{len(lines)} lines match no known template")

        score = min(1.0, worst)
        return Detection(
            detector=self.name, label="anomaly" if score >= 0.5 else "benign",
            score=score, category="log_anomaly" if score >= 0.5 else None,
            explanation=("; ".join(reasons[:4]) if reasons
                         else "all templates match known-good baseline"),
        )

    @staticmethod
    def _featurize(line: str) -> list[float]:
        t = _template(line)
        return [
            len(t) / 100.0,
            t.count("<N>") / 10.0,
            t.count("<IP>") / 5.0,
            1.0 if "ERROR" in line or "FATAL" in line or "CRITICAL" in line else 0.0,
            1.0 if "root" in line or "sudo" in line else 0.0,
            1.0 if "Failed password" in line or "authentication failure" in line.lower() else 0.0,
        ]
