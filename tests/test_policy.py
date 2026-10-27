from app.detection.base import Detection
from app.policy.engine import PolicyEngine


def make(det_name: str, score: float, spans=None) -> Detection:
    return Detection(detector=det_name, label=det_name, score=score,
                     spans=spans or [])


def test_block_wins_over_redact():
    eng = PolicyEngine()
    decision = eng.evaluate("default", [
        make("pii", 0.9, spans=[{"start": 0, "end": 5, "type": "email", "sensitivity": 0.6}]),
        make("prompt_injection", 0.95),
    ])
    assert decision.action == "block"


def test_redact_action_carries_spans():
    eng = PolicyEngine()
    spans = [{"start": 3, "end": 10, "type": "email", "sensitivity": 0.6}]
    decision = eng.evaluate("default", [make("pii", 0.8, spans=spans)])
    assert decision.action == "redact"
    assert decision.redact_spans == spans
    assert decision.reasons


def test_low_scores_allow():
    eng = PolicyEngine()
    decision = eng.evaluate("default", [make("pii", 0.1), make("prompt_injection", 0.2)])
    assert decision.action == "allow"


def test_escalate_above_high_anomaly():
    eng = PolicyEngine()
    decision = eng.evaluate("default", [make("log_anomaly", 0.95)])
    assert decision.action == "escalate"


def test_unknown_tenant_falls_back_to_default():
    eng = PolicyEngine()
    decision = eng.evaluate("no-such-tenant", [make("prompt_injection", 0.95)])
    assert decision.action == "block"
