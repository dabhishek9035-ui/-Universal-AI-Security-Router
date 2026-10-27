"""Security pipeline: the request path through the whole system.

type detect -> learned route -> detectors (parallel) -> policy decision ->
redact/block -> audit -> (chat: LLM route -> output guard).
"""
from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from . import metrics
from .audit import get_audit_log
from .detection import get_detectors
from .detection.base import Detection
from .detection.output_guard import guard_response
from .detection.pii_dlp import redact_text
from .detection.type_detector import detect_type
from .llm import complete as llm_complete, LLMNotConfigured
from .policy import get_policy_engine
from .router import SecurityRouter, route_llm
from .schemas import ChatRequest, ChatResponse, DetectionOut, InputPayload, RouterDecisionOut, ScanResponse

_executor = ThreadPoolExecutor(max_workers=8)
_router = SecurityRouter()
_feedback_memory: OrderedDict[str, dict[str, Any]] = OrderedDict()
_MEMORY_MAX = 1000


def get_security_router() -> SecurityRouter:
    return _router


def _run_detector(name: str, payload: InputPayload, input_type: str) -> Detection:
    det = next(d for d in get_detectors() if d.name == name)
    start = time.perf_counter()
    result = det.predict(payload, input_type)
    result.latency_ms = (time.perf_counter() - start) * 1000  # type: ignore[attr-defined]
    return result


def scan(payload: InputPayload, strategy: str = "bandit") -> ScanResponse:
    start = time.perf_counter()
    request_id = str(uuid.uuid4())
    text = payload.text or ""

    input_type, type_conf = detect_type(text, payload.declared_type, payload.meta)

    run_names, skipped, router_info = _router.route(payload, input_type, strategy)
    router_out = RouterDecisionOut(
        strategy=router_info.get("strategy", strategy),
        detectors_run=list(run_names),
        skipped=list(skipped),
        context=router_info.get("context", {}),
    )

    # run chosen detectors in parallel threads
    futures = {name: _executor.submit(_run_detector, name, payload, input_type)
               for name in run_names}
    detections: list[Detection] = []
    det_latencies: dict[str, float] = {}
    for name, fut in futures.items():
        det: Detection = fut.result()
        det_latencies[name] = getattr(det, "latency_ms", 0.0)
        detections.append(det)

    decision = get_policy_engine().evaluate(payload.tenant, detections, text)

    redacted_text = None
    if decision.action in ("redact", "escalate") and decision.redact_spans:
        redacted_text = redact_text(text, decision.redact_spans)

    latency_ms = (time.perf_counter() - start) * 1000

    metrics.record_scan(decision.action, input_type, router_out.strategy,
                        run_names, latency_ms, det_latencies)
    get_audit_log().append(
        request_id=request_id, tenant=payload.tenant, input_type=input_type,
        input_hash=hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest(),
        decision=decision.action, reasons=decision.reasons,
        detections=[d.to_out() for d in detections],
        router=router_out.model_dump(), latency_ms=round(latency_ms, 2),
    )
    # remember enough to apply labeled feedback later
    _feedback_memory[request_id] = {
        "payload": payload, "input_type": input_type,
        "detectors_run": list(run_names), "latency_ms": latency_ms,
        "decision": decision.action,
    }
    while len(_feedback_memory) > _MEMORY_MAX:
        _feedback_memory.popitem(last=False)

    return ScanResponse(
        request_id=request_id, tenant=payload.tenant, input_type=input_type,
        decision=decision.action, reasons=decision.reasons,
        detections=[DetectionOut(**d.to_out()) for d in detections],
        redacted_text=redacted_text, router=router_out,
        latency_ms=round(latency_ms, 2),
    )


def apply_feedback(request_id: str, actual: str) -> dict:
    """Labeled feedback -> bandit reward update (correctness - cost - latency)."""
    entry = _feedback_memory.get(request_id)
    if entry is None:
        return {"updated": False, "detail": "request not found in recent memory"}
    actual = actual.lower()
    if actual not in ("malicious", "benign"):
        return {"updated": False, "detail": "actual must be 'malicious' or 'benign'"}
    decision = entry["decision"]
    detected = decision in ("block", "redact", "escalate", "flag")
    correct = detected if actual == "malicious" else decision == "allow"
    reward = _router.update_reward(
        entry["payload"], entry["input_type"], entry["detectors_run"],
        correct, entry["latency_ms"],
    )
    _router.save()
    return {"updated": True, "request_id": request_id,
            "decision_was": decision, "correct": correct, "bandit_reward": reward}


async def chat(req: ChatRequest) -> ChatResponse:
    scan_result = scan(InputPayload(**req.model_dump(exclude={"system", "force_tier"})))

    base = scan_result.model_dump()
    if scan_result.decision == "block":
        return ChatResponse(**base, answer=None,
                            llm={"status": "blocked", "reason": "input blocked by policy"})

    llm_info = route_llm(InputPayload(text=req.text), req.force_tier)
    llm_info["status"] = "ok"
    try:
        result = await llm_complete(req.text, llm_info["tier"], req.system)
        answer = result["text"]
        llm_info.update({k: result[k] for k in ("model", "backend", "latency_ms")})
    except LLMNotConfigured as e:
        answer = None
        llm_info["status"] = "unconfigured"
        llm_info["detail"] = str(e)
        metrics.record_llm_call("none")
    except Exception as e:  # LLM infra failures must never fail the request
        answer = None
        llm_info["status"] = "error"
        llm_info["detail"] = str(e)
        metrics.record_llm_call("none")

    output_guard: list[DetectionOut] = []
    if answer:
        metrics.record_llm_call(llm_info["tier"])
        cleaned, guard_dets = guard_response(answer)
        if cleaned != answer:
            answer = cleaned
        for gd in guard_dets:
            output_guard.append(DetectionOut(**gd))

    return ChatResponse(**base, answer=answer, llm=llm_info, output_guard=output_guard)
