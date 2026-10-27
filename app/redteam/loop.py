"""Closed-loop adversarial retraining.

generate attacks -> run through the live pipeline (sandboxed, internal) ->
record misses -> hard-example buffer -> learn patterns / bandit rewards ->
re-measure attack success rate (ASR) per category.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from collections import Counter

from .. import config
from ..detection.prompt_injection import add_learned_pattern
from ..pipeline import scan
from ..schemas import InputPayload
from .attacks import Attack, generate_attacks


def _is_miss(attack: Attack, decision: str) -> bool:
    if attack.expected_action == "allow":
        return decision in ("block", "escalate")  # false positive on benign
    if attack.expected_action == "block":
        return decision not in ("block", "escalate")
    if attack.expected_action == "redact":
        return decision not in ("redact", "block", "escalate")
    return False


def _distinctive_fragment(text: str) -> str | None:
    """A short regex-safe fragment to learn from a missed injection."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned or len(cleaned) < 12:
        return None
    fragment = cleaned[:60]
    return re.escape(fragment[:40])


def run_round(n_attacks: int = 40, round_name: str = "", strategy: str = "bandit",
              learn: bool = True) -> dict:
    """Run one red-team round; returns the round summary dict."""
    config.ensure_dirs()
    attacks = generate_attacks(n_attacks)
    round_id = round_name or f"round-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    results: list[dict] = []
    category_stats: dict[str, Counter] = {}
    misses: list[dict] = []

    for attack in attacks:
        resp = scan(InputPayload(text=attack.text, tenant="default"), strategy=strategy)
        missed = _is_miss(attack, resp.decision)
        stat = category_stats.setdefault(attack.category, Counter())
        stat["total"] += 1
        stat["missed" if missed else "caught"] += 1
        entry = {
            "category": attack.category, "mutation": attack.mutation,
            "expected": attack.expected_action, "decision": resp.decision,
            "missed": missed, "text_preview": attack.text[:160],
            "input_type": resp.input_type,
            "detectors_run": resp.router.detectors_run,
            "latency_ms": resp.latency_ms,
        }
        results.append(entry)
        if missed:
            misses.append(entry)
            # hard-example buffer
            with open(config.HARD_EXAMPLES_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "text": attack.text, "category": attack.category,
                    "expected": attack.expected_action,
                    "decision": resp.decision, "ts": time.time(),
                }) + "\n")
            if learn and attack.category in ("injection", "override", "jailbreak",
                                             "fake_system", "tool_abuse", "exfil",
                                             "phishing"):
                frag = _distinctive_fragment(attack.text)
                if frag:
                    # weight 3.5: a confirmed miss is strong evidence; a single
                    # learned hit (sigmoid(3.5-2)~0.82) plus any model signal
                    # must reach the block threshold (0.85)
                    add_learned_pattern(frag, weight=3.5,
                                        category=f"learned_{attack.category}")

    # bandit reward for the arm that actually ran (correctness - cost - latency)
    from ..pipeline import get_security_router
    router = get_security_router()
    for attack, entry in zip(attacks, results):
        correct = (not entry["missed"]) if attack.expected_action != "allow" \
            else entry["decision"] == "allow"
        router.update_reward(
            InputPayload(text=attack.text), entry["input_type"],
            detectors_run=entry["detectors_run"], correct=correct,
            total_latency_ms=entry["latency_ms"],
        )
    router.save()

    asr = {cat: round(c["missed"] / c["total"], 3)
           for cat, c in category_stats.items()}
    total = sum(c["total"] for c in category_stats.values())
    total_missed = sum(c["missed"] for c in category_stats.values())
    summary = {
        "round_id": round_id,
        "ts": time.time(),
        "strategy": strategy,
        "n_attacks": total,
        "misses": total_missed,
        "asr_overall": round(total_missed / total, 3) if total else 0.0,
        "asr_by_category": asr,
        "miss_details": misses,
        "false_positives_on_benign": category_stats.get("benign", Counter()).get("missed", 0),
    }
    with open(config.REDTEAM_HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")
    return summary


def load_history(limit: int = 20) -> list[dict]:
    if not config.REDTEAM_HISTORY_PATH.exists():
        return []
    rows = []
    with open(config.REDTEAM_HISTORY_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


def benchmark(before: bool = True) -> dict:
    """Fixed benchmark set for before/after comparison across retraining."""
    return run_round(n_attacks=40, round_name=f"benchmark-{'before' if before else 'after'}",
                     strategy="all", learn=False)
