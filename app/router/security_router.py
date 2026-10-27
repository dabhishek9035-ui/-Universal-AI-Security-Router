"""Learned Security Router.

Context = input features (type one-hot, log length, entropy, tenant).
Arms = detector subsets: mandatory base for the input type, plus zero or more
optional detectors. Strategies: 'bandit' (LinUCB), 'rules' (cold start /
baseline), 'all' (run-everything baseline).
"""
from __future__ import annotations

import threading

import numpy as np

from .. import config
from ..detection import BaseDetector, get_detectors
from ..detection.base import shannon_entropy
from ..schemas import InputPayload
from .bandit import LinUCB

CONTEXT_FEATURES = [
    "bias", "log_len", "entropy", "tenant_risk",
    "type_prompt", "type_email", "type_url", "type_log", "type_file", "type_traffic",
]
DIM = len(CONTEXT_FEATURES)

# Rules-only cold start: detectors we always run for a given input type.
MANDATORY: dict[str, tuple[str, ...]] = {
    "prompt": ("prompt_injection", "pii"),
    "email": ("pii", "phishing"),
    "url": ("phishing",),
    "log": ("log_anomaly",),
    "file": ("malware", "pii"),
    "traffic": ("log_anomaly",),
}


def context_vector(payload: InputPayload, input_type: str) -> np.ndarray:
    text = payload.text or ""
    tenant_risk = 1.0 if (payload.meta or {}).get("untrusted_source") else 0.0
    type_onehot = [1.0 if input_type == t else 0.0 for t in
                   ("prompt", "email", "url", "log", "file", "traffic")]
    return np.array(
        [1.0, min(len(text), 4000) / 1000.0, shannon_entropy(text) / 5.0, tenant_risk,
         *type_onehot],
        dtype=float,
    )


def candidate_arms(input_type: str, detectors: list[BaseDetector]) -> tuple[list[str], list[str]]:
    """Returns (mandatory, optional) detector names applicable to this type."""
    applicable = [d.name for d in detectors if d.applies_to(input_type)]
    mandatory = [m for m in MANDATORY.get(input_type, ()) if m in applicable]
    optional = [d for d in applicable if d not in mandatory]
    return mandatory, optional


class SecurityRouter:
    def __init__(self):
        self._lock = threading.Lock()
        self._bandit: LinUCB | None = None

    def _get_bandit(self) -> LinUCB:
        with self._lock:
            if self._bandit is None:
                self._bandit = LinUCB.load(config.BANDIT_STATE_PATH) \
                    or LinUCB(dim=DIM, alpha=config.BANDIT_ALPHA)
            return self._bandit

    def save(self) -> None:
        with self._lock:
            if self._bandit is not None:
                config.ensure_dirs()
                self._bandit.save(config.BANDIT_STATE_PATH)

    def route(
        self,
        payload: InputPayload,
        input_type: str,
        strategy: str = "bandit",
    ) -> tuple[list[str], list[str], dict]:
        """Returns (detectors_to_run, skipped, info)."""
        detectors = get_detectors()
        mandatory, optional = candidate_arms(input_type, detectors)
        context = context_vector(payload, input_type)

        if strategy == "all":
            run = mandatory + optional
            return run, [], {"strategy": "all", "context": self._ctx_dict(context)}

        if strategy == "rules":
            return list(mandatory), list(optional), {
                "strategy": "rules", "context": self._ctx_dict(context)}

        # bandit: choose how many optional detectors to add (0..n), learned per subset
        bandit = self._get_bandit()
        subsets: dict[str, list[str]] = {"base_only": list(mandatory)}
        for i, opt in enumerate(optional):
            subsets[f"base+{'+'.join(optional[:i + 1])}"] = mandatory + optional[:i + 1]
        arm_ids = list(subsets)
        best_arm, scores = bandit.select(context, arm_ids)
        run = subsets[best_arm]
        skipped = [d for d in mandatory + optional if d not in run]
        return run, skipped, {
            "strategy": "bandit",
            "arm": best_arm,
            "ucb_scores": {k: round(v, 3) for k, v in scores.items()},
            "context": self._ctx_dict(context),
        }

    @staticmethod
    def _ctx_dict(context: np.ndarray) -> dict:
        return {k: round(float(v), 3) for k, v in zip(CONTEXT_FEATURES, context)}

    def update_reward(
        self, payload: InputPayload, input_type: str,
        detectors_run: list[str], correct: bool,
        total_latency_ms: float,
    ) -> float:
        """reward = correctness - cost_weight*sum(cost) - latency_weight*latency."""
        detectors = {d.name: d for d in get_detectors()}
        cost = sum(detectors[d].cost for d in detectors_run if d in detectors)
        reward = (1.0 if correct else 0.0) \
            - config.BANDIT_COST_WEIGHT * cost \
            - config.BANDIT_LATENCY_WEIGHT * (total_latency_ms / 100.0)
        reward = max(-1.0, min(1.0, reward))

        bandit = self._get_bandit()
        context = context_vector(payload, input_type)
        mandatory, optional = candidate_arms(input_type, list(detectors.values()))
        subsets: dict[str, list[str]] = {"base_only": list(mandatory)}
        for i, opt in enumerate(optional):
            subsets[f"base+{'+'.join(optional[:i + 1])}"] = mandatory + optional[:i + 1]
        arm = None
        for arm_id, members in subsets.items():
            if set(members) == set(detectors_run):
                arm = arm_id
                break
        if arm is None:
            arm = "base_only"
        bandit.update(arm, context, reward)
        return round(reward, 4)
