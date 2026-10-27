"""Detector registry — single shared instances, discovered by the router."""
from __future__ import annotations

from .base import BaseDetector, Detection
from .log_anomaly import LogAnomalyDetector, fit_baseline
from .malware import MalwareDetector
from .phishing import PhishingDetector
from .pii_dlp import PIIDetector
from .prompt_injection import PromptInjectionDetector

_instances: list[BaseDetector] | None = None


def get_detectors() -> list[BaseDetector]:
    global _instances
    if _instances is None:
        _instances = [
            PromptInjectionDetector(),
            PIIDetector(),
            PhishingDetector(),
            LogAnomalyDetector(),
            MalwareDetector(),
        ]
    return _instances


def get_detector(name: str) -> BaseDetector | None:
    for d in get_detectors():
        if d.name == name:
            return d
    return None


__all__ = [
    "BaseDetector", "Detection", "get_detectors", "get_detector",
    "PromptInjectionDetector", "PIIDetector", "PhishingDetector",
    "LogAnomalyDetector", "MalwareDetector", "fit_baseline",
]
