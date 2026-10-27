"""Per-tenant policy engine.

YAML rules with hot-reload on mtime change. Precedence: block > escalate >
redact > flag > allow. Rules are evaluated per detector against thresholds;
the final decision keeps every triggered rule as an explanation ("blocked
because ...").
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .. import config
from ..detection.base import Detection

ACTION_PRECEDENCE = {"allow": 0, "flag": 1, "redact": 2, "escalate": 3, "block": 4}


@dataclass
class PolicyDecision:
    action: str = "allow"
    reasons: list[str] = field(default_factory=list)
    redact_spans: list[dict] = field(default_factory=list)


class PolicyEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, dict]] = {}

    def _load_policy(self, tenant: str) -> dict:
        """Per-tenant YAML with fallback to default.yaml, hot-reloaded on mtime."""
        path = config.POLICY_DIR / f"{tenant}.yaml"
        fallback = config.POLICY_DIR / "default.yaml"
        target = path if path.exists() else fallback
        mtime = target.stat().st_mtime if target.exists() else 0.0
        with self._lock:
            cached = self._cache.get(tenant)
            if cached and cached[0] == mtime:
                return cached[1]
        with open(target, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        data.setdefault("rules", [])
        with self._lock:
            self._cache[tenant] = (mtime, data)
        return data

    def save_policy(self, tenant: str, data: dict) -> Path:
        """Used by the dashboard policy editor; validated before write."""
        if not isinstance(data, dict) or not isinstance(data.get("rules", []), list):
            raise ValueError("policy must be a mapping with a 'rules' list")
        for rule in data["rules"]:
            if rule.get("action") not in ACTION_PRECEDENCE:
                raise ValueError(f"invalid action in rule: {rule}")
        config.POLICY_DIR.mkdir(parents=True, exist_ok=True)
        path = config.POLICY_DIR / f"{tenant}.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False)
        with self._lock:
            self._cache.pop(tenant, None)
        return path

    def evaluate(self, tenant: str, detections: list[Detection],
                 text: str = "") -> PolicyDecision:
        policy = self._load_policy(tenant)
        decision = PolicyDecision()
        triggered: list[str] = []

        for rule in policy.get("rules", []):
            det_name = rule.get("detector")
            threshold = float(rule.get("above", 1.1))
            action = rule.get("action", "flag")
            for det in detections:
                if det.detector != det_name or det.score < threshold:
                    continue
                reason = (f"{det_name} score {det.score:.2f} > {threshold:g} -> {action}"
                          f" (category: {det.category})" if det.category else
                          f"{det_name} score {det.score:.2f} > {threshold:g} -> {action}")
                if reason not in triggered:
                    triggered.append(reason)
                if ACTION_PRECEDENCE[action] > ACTION_PRECEDENCE[decision.action]:
                    decision.action = action
                if action == "redact" and det.spans:
                    decision.redact_spans.extend(det.spans)

        # denylist / allowlist exact-match overrides
        deny = [p for p in policy.get("denylist", []) if p and p in text]
        if deny and decision.action != "block":
            decision.action = "block"
            triggered.append(f"denylist match: {deny[0][:40]}")
        if policy.get("allowlist") and decision.action in ("block", "escalate"):
            allow = [p for p in policy["allowlist"] if p and p in text]
            if allow:
                decision.action = "flag"
                triggered.append(f"allowlist match: {allow[0][:40]}")

        decision.reasons = triggered
        # de-duplicate overlapping redact spans, keep highest sensitivity
        uniq: dict[tuple[int, int], dict] = {}
        for sp in decision.redact_spans:
            key = (sp["start"], sp["end"])
            if key not in uniq or sp.get("sensitivity", 0) > uniq[key].get("sensitivity", 0):
                uniq[key] = sp
        decision.redact_spans = sorted(uniq.values(), key=lambda s: s["start"])
        return decision


_engine: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine
