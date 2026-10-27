"""Shared detector interface. Every specialist implements predict()."""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..schemas import InputPayload


@dataclass
class Detection:
    detector: str
    label: str = "benign"          # e.g. "injection", "pii", "benign"
    score: float = 0.0             # calibrated-ish 0..1, higher = more malicious
    category: str | None = None    # fine-grained: "jailbreak", "credit_card", ...
    explanation: str = ""
    spans: list[dict[str, Any]] = field(default_factory=list)  # {start,end,type}

    def to_out(self) -> dict[str, Any]:
        return {
            "detector": self.detector,
            "label": self.label,
            "score": round(self.score, 4),
            "category": self.category,
            "explanation": self.explanation,
            "spans": self.spans,
        }


class BaseDetector(ABC):
    name: str = "base"
    input_types: tuple[str, ...] = ("prompt", "email", "url", "log", "file", "traffic")
    cost: float = 1.0          # relative compute cost, used by the router reward
    latency_ms: float = 5.0    # rough expected latency, used for cold-start routing

    @abstractmethod
    def predict(self, payload: InputPayload, input_type: str) -> Detection: ...

    def applies_to(self, input_type: str) -> bool:
        return input_type in self.input_types


def shannon_entropy(text: str) -> float:
    """Entropy per character over the visible charset; 0 for empty text."""
    if not text:
        return 0.0
    freq: dict[str, int] = {}
    for ch in text:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(text)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    return math.exp(x) / (1.0 + math.exp(x))
