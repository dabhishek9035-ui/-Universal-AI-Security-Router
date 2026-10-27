"""API request/response models."""
from typing import Any, Optional

from pydantic import BaseModel, Field

INPUT_TYPES = ("prompt", "email", "url", "log", "file", "traffic")


class InputPayload(BaseModel):
    text: str = ""
    declared_type: str = Field(
        default="auto",
        description="auto | prompt | email | url | log | file | traffic",
    )
    meta: dict[str, Any] = Field(default_factory=dict)
    tenant: str = "default"


class DetectionOut(BaseModel):
    detector: str
    label: str = "benign"
    score: float = 0.0
    category: Optional[str] = None
    explanation: str = ""
    spans: list[dict[str, Any]] = Field(default_factory=list)


class RouterDecisionOut(BaseModel):
    strategy: str  # bandit | rules | all
    detectors_run: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class ScanResponse(BaseModel):
    request_id: str
    tenant: str
    input_type: str
    decision: str  # allow | block | redact | flag | escalate
    reasons: list[str] = Field(default_factory=list)
    detections: list[DetectionOut] = Field(default_factory=list)
    redacted_text: Optional[str] = None
    router: RouterDecisionOut
    latency_ms: float = 0.0


class ChatRequest(InputPayload):
    system: Optional[str] = None
    force_tier: Optional[str] = Field(
        default=None, description="'local' or 'big' to bypass the LLM router"
    )


class ChatResponse(ScanResponse):
    answer: Optional[str] = None
    llm: dict[str, Any] = Field(default_factory=dict)
    output_guard: list[DetectionOut] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    request_id: str
    actual: str = Field(description="'malicious' or 'benign'")
    note: str = ""


class RedTeamRequest(BaseModel):
    n_attacks: int = Field(default=40, ge=1, le=500)
    round_name: str = ""
