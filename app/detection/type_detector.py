"""Input Type Detector.

Stage 1: deterministic rules (URL shape, email headers, log formats, file
extensions, flow-feature presence). Stage 2 (optional): a trained TF-IDF
classifier at models/input_type.joblib is used when rules are not confident.
Returns (type, confidence).
"""
from __future__ import annotations

import re

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
EMAIL_HEADER_RE = re.compile(
    r"^(from|to|subject|received|reply-to|message-id|dkim-signature):", re.MULTILINE | re.IGNORECASE
)
EMAIL_ADDR_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
LOG_LINE_RE = re.compile(
    r"^\[?\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) +\d{1,2} +\d{2}:\d{2}:\d{2}\b"
    r"|^\w+\[\d+\]:",
    re.MULTILINE,
)
LOG_LEVEL_RE = re.compile(r"\b(?:INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL|DEBUG|TRACE)\b")
SYSLOG_RE = re.compile(r"<\d{1,3}>\w{3} +\d{1,2} \d{2}:\d{2}:\d{2} [\w.-]+")

RISKY_EXTENSIONS = {
    ".exe", ".dll", ".scr", ".bat", ".cmd", ".ps1", ".js", ".vbs", ".jar",
    ".apk", ".docm", ".xlsm", ".pptm", ".hta", ".msi", ".sh",
}

RULE_CONFIDENCE = 0.95


def detect_type(text: str, declared: str, meta: dict) -> tuple[str, float]:
    if declared != "auto":
        return declared, 1.0

    # Explicit meta wins (multipart uploads, SDK hints).
    if meta.get("filename"):
        return "file", RULE_CONFIDENCE
    if meta.get("flow_features") is not None:
        return "traffic", RULE_CONFIDENCE
    if meta.get("email_headers") is not None:
        return "email", RULE_CONFIDENCE

    stripped = text.strip()
    # A bare URL (possibly with surrounding whitespace) is unambiguous.
    if stripped and URL_RE.fullmatch(stripped):
        return "url", RULE_CONFIDENCE

    if EMAIL_HEADER_RE.search(text) or (text.count("@") >= 1 and EMAIL_HEADER_RE.search(text)):
        return "email", RULE_CONFIDENCE

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if lines:
        logish = sum(
            1 for ln in lines
            if LOG_LINE_RE.search(ln) or SYSLOG_RE.search(ln)
            or (LOG_LEVEL_RE.search(ln) and len(ln.split()) >= 4)
        )
        if logish / len(lines) >= 0.6:
            return "log", RULE_CONFIDENCE

    if URL_RE.search(stripped) and len(stripped) < 500 and " " not in stripped.strip():
        return "url", 0.8

    # File-content heuristics: MZ header, base64-ish blob with risky extension hint
    if stripped.startswith("MZ") or meta.get("content_b64"):
        return "file", 0.85

    trained = _trained_type(text)
    if trained:
        return trained

    return "prompt", 0.75


_classifier = None
_classifier_loaded = False


def _trained_type(text: str) -> tuple[str, float] | None:
    """Optional stage-2 classifier, produced by scripts/train_type_detector.py."""
    global _classifier, _classifier_loaded
    if not _classifier_loaded:
        _classifier_loaded = True
        try:
            import joblib
            from .. import config
            path = config.MODELS_DIR / "input_type.joblib"
            if path.exists():
                _classifier = joblib.load(path)
        except Exception:
            _classifier = None
    if _classifier is None:
        return None
    try:
        proba = _classifier.predict_proba([text])[0]
        idx = proba.argmax()
        if proba[idx] < 0.6:
            return None
        return str(_classifier.classes_[idx]), float(proba[idx])
    except Exception:
        return None
