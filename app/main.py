"""FastAPI application: security gateway + ops dashboard."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from . import config, metrics
from .audit import get_audit_log
from .detection.prompt_injection import load_learned_patterns
from .gateway import Tenant, rate_limit, require_tenant
from .pipeline import apply_feedback, chat, scan
from .schemas import ChatRequest, ChatResponse, FeedbackRequest, InputPayload, ScanResponse
from .dashboard.api import router as dashboard_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    get_audit_log()          # init db + genesis row
    load_learned_patterns()  # red-team learned patterns
    yield


app = FastAPI(
    title="Universal AI Security Router",
    description="One plug-and-play security layer in front of any app or LLM: "
                "learned detector routing, policy engine, red-team loop.",
    version="0.1.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard() -> HTMLResponse:
    return HTMLResponse(Path(config.DASHBOARD_TEMPLATE).read_text(encoding="utf-8"))


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "audit_chain": get_audit_log().verify()["ok"]}


@app.post("/v1/scan", response_model=ScanResponse,
          dependencies=[Depends(rate_limit)])
def v1_scan(payload: InputPayload, tenant: Tenant = Depends(require_tenant)) -> ScanResponse:
    """Scan any input; returns decision, detections and (if redacted) clean text."""
    payload.tenant = tenant.name
    return scan(payload)


@app.post("/v1/chat", response_model=ChatResponse,
          dependencies=[Depends(rate_limit)])
async def v1_chat(req: ChatRequest, tenant: Tenant = Depends(require_tenant)) -> ChatResponse:
    """Guarded LLM completion: scan input, route to local/big model, guard output."""
    req.tenant = tenant.name
    return await chat(req)


@app.post("/v1/feedback")
def v1_feedback(feedback: FeedbackRequest, tenant: Tenant = Depends(require_tenant)) -> dict:
    """Labeled feedback ('malicious'/'benign') -> online bandit update."""
    return apply_feedback(feedback.request_id, feedback.actual)


app.include_router(dashboard_router)
