"""PII / secret-leak (DLP) detector.

Pure-regex + Luhn stage (always on, gives exact spans for redaction), plus an
optional trained NER/TF-IDF stage hook. Spans feed the policy engine's redact
action directly.
"""
from __future__ import annotations

import re

from .base import BaseDetector, Detection

# (compiled regex, pii_type, sensitivity 0..1, label shown to user)
_PATTERNS: list[tuple[re.Pattern, str, float]] = [
    # --- secrets / credentials (highest sensitivity) ---
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "aws_access_key", 1.0),
    (re.compile(r"(?i)\baws(.{0,20})?['\"][0-9a-zA-Z/+]{40}['\"]"), "aws_secret_key", 1.0),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "github_token", 1.0),
    (re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"), "openai_api_key", 1.0),
    (re.compile(r"\bgsk_[A-Za-z0-9]{20,}\b"), "groq_api_key", 1.0),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "slack_token", 1.0),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b"), "jwt", 0.95),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP |DSA )?PRIVATE KEY( BLOCK)?-----"), "private_key", 1.0),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "google_api_key", 1.0),
    (re.compile(r"\b[0-9a-f]{32}(?:[0-9a-f]{8})?\b(?=.{0,30}(?:password|secret|token|key))", re.IGNORECASE), "hex_secret", 0.7),
    (re.compile(r"(?i)\b(?:password|passwd|pwd|secret)\s*[:=]\s*['\"]?([^\s'\"]{6,})"), "password_field", 0.85),
    # --- financial ---
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "credit_card", 0.95),   # Luhn-checked below
    (re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"), "iban", 0.7),
    # --- government ids ---
    (re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b"), "aadhaar_like", 0.9),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "ssn", 0.95),
    # --- contact / network ---
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b"), "email", 0.6),
    (re.compile(r"\b(?:\+?\d{1,3}[-. ]?)?(?:\(\d{2,4}\)[-. ]?)?\d{3}[-. ]?\d{4}\b"), "phone", 0.55),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "ip_address", 0.5),
    (re.compile(r"\b(?:https?:\/\/)?[\w.-]+:[\w.%!+-]+@(?:[\w.-]+)\b"), "url_credentials", 0.9),
]

_LUHN_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn_ok(number: str) -> bool:
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _false_positive(text: str, start: int, end: int, pii_type: str) -> bool:
    """Cheap context checks to cut obvious FP noise."""
    window = text[max(0, start - 30):min(len(text), end + 30)].lower()
    if pii_type == "credit_card":
        # Luhn already gates; but skip version-like strings
        return not _luhn_ok(text[start:end])
    if pii_type == "phone":
        # pure years / small numbers / timestamps
        raw = text[start:end]
        return raw.startswith(("19", "20")) and len(raw) == 4
    if pii_type == "ip_address":
        return "version" in window or "port" in window and "ip" not in window
    if pii_type == "iban":
        return "http" in window  # matches inside URLs like /TR123...
    return False


REDACT_MASK = "[REDACTED:{type}]"


def redact_text(text: str, spans: list[dict]) -> str:
    """Replace spans (right-to-left so indices stay valid)."""
    out = text
    for span in sorted(spans, key=lambda s: s["start"], reverse=True):
        s, e = span["start"], span["end"]
        out = out[:s] + REDACT_MASK.format(type=span["type"]) + out[e:]
    return out


class PIIDetector(BaseDetector):
    name = "pii"
    input_types = ("prompt", "email", "url", "log", "file")
    cost = 0.6
    latency_ms = 2.0

    def predict(self, payload, input_type: str) -> Detection:
        text = payload.text or ""
        spans: list[dict] = []
        seen: set[tuple[int, int]] = set()

        for regex, pii_type, sensitivity in _PATTERNS:
            for m in regex.finditer(text):
                s, e = m.span()
                if (s, e) in seen or e <= s:
                    continue
                # skip if inside an already-caught higher-sensitivity span
                if any(ss <= s and e <= ee for ss, ee in seen):
                    continue
                if _false_positive(text, s, e, pii_type):
                    continue
                seen.add((s, e))
                spans.append({"start": s, "end": e, "type": pii_type,
                              "sensitivity": sensitivity})

        spans.sort(key=lambda sp: sp["start"])
        # de-overlap greedy from the left, prefer higher sensitivity
        final: list[dict] = []
        for sp in spans:
            if final and sp["start"] < final[-1]["end"]:
                if sp["sensitivity"] > final[-1]["sensitivity"]:
                    final[-1] = sp
                continue
            final.append(sp)

        if not final:
            return Detection(detector=self.name, label="benign", score=0.0,
                             explanation="no PII/secrets detected")

        max_sens = max(sp["sensitivity"] for sp in final)
        # score grows with sensitivity and volume, saturates near 1
        score = min(1.0, max_sens + 0.08 * (len(final) - 1))
        types = sorted({sp["type"] for sp in final})
        return Detection(
            detector=self.name, label="pii", score=score,
            category=types[0],
            explanation=f"found {len(final)} item(s): {', '.join(types)}",
            spans=final,
        )
