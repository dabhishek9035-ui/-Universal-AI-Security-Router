"""Thread-safe in-process metrics for the dashboard and monitoring."""
import threading
import time
from collections import deque

from . import config

_lock = threading.Lock()
_state = {
    "requests_total": 0,
    "decisions": {"allow": 0, "block": 0, "redact": 0, "flag": 0, "escalate": 0},
    "by_input_type": {},
    "detector_runs": {},
    "llm_tier_calls": {"local": 0, "big": 0, "none": 0},
    "router_strategy_counts": {"bandit": 0, "rules": 0, "all": 0},
}
_latencies: deque[float] = deque(maxlen=2000)
_detector_latencies: dict[str, deque] = {}


def record_scan(decision: str, input_type: str, strategy: str,
                detectors_run: list[str], latency_ms: float,
                detector_latencies: dict[str, float]) -> None:
    with _lock:
        _state["requests_total"] += 1
        _state["decisions"][decision] = _state["decisions"].get(decision, 0) + 1
        _state["by_input_type"][input_type] = _state["by_input_type"].get(input_type, 0) + 1
        _state["router_strategy_counts"][strategy] = \
            _state["router_strategy_counts"].get(strategy, 0) + 1
        for d in detectors_run:
            _state["detector_runs"][d] = _state["detector_runs"].get(d, 0) + 1
        _latencies.append(latency_ms)
        for name, ms in detector_latencies.items():
            buf = _detector_latencies.setdefault(name, deque(maxlen=500))
            buf.append(ms)


def record_llm_call(tier: str) -> None:
    with _lock:
        key = tier if tier in _state["llm_tier_calls"] else "none"
        _state["llm_tier_calls"][key] += 1


def _pctl(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, int(p / 100 * len(sorted_vals)))
    return round(sorted_vals[idx], 2)


def snapshot() -> dict:
    with _lock:
        lat = sorted(_latencies)
        det_p95 = {
            name: _pctl(sorted(buf), 95) for name, buf in _detector_latencies.items()
        }
        base = {k: (dict(v) if isinstance(v, dict) else v) for k, v in _state.items()}
    tiers = base["llm_tier_calls"]
    total_llm = tiers["local"] + tiers["big"]
    cost_actual = (
        tiers["big"] * config.COST_BIG_PER_1K * config.AVG_RESPONSE_TOKENS / 1000
        + tiers["local"] * config.COST_LOCAL_PER_1K * config.AVG_RESPONSE_TOKENS / 1000
    )
    cost_always_big = total_llm * config.COST_BIG_PER_1K * config.AVG_RESPONSE_TOKENS / 1000
    return {
        **base,
        "latency_ms": {"p50": _pctl(lat, 50), "p95": _pctl(lat, 95)},
        "detector_latency_p95_ms": det_p95,
        "cost": {
            "usd_actual": round(cost_actual, 4),
            "usd_if_always_big": round(cost_always_big, 4),
            "usd_saved": round(cost_always_big - cost_actual, 4),
            "est_savings_pct": round(
                100 * (1 - cost_actual / cost_always_big) if cost_always_big else 0.0, 1
            ),
        },
    }
