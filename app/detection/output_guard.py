"""Output Guard: re-scan LLM responses for leaks / unsafe content before returning."""
from __future__ import annotations

from ..schemas import InputPayload
from .pii_dlp import PIIDetector, redact_text
from .prompt_injection import PromptInjectionDetector


def guard_response(answer: str) -> tuple[str, list[dict]]:
    """Returns (possibly redacted answer, list of detection dicts)."""
    pii = PIIDetector().predict(InputPayload(text=answer), "prompt")
    inj = PromptInjectionDetector().predict(InputPayload(text=answer), "prompt")

    out: list[dict] = []
    cleaned = answer
    if pii.label == "pii":
        cleaned = redact_text(cleaned, pii.spans)
        out.append(pii.to_out())
    # injected instructions echoed back by the model are flagged, not stripped
    if inj.label == "injection":
        inj.explanation = "output guard: " + inj.explanation
        out.append(inj.to_out())
    return cleaned, out
