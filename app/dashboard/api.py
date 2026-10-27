"""Ops/dashboard API: metrics, audit viewer, policy editor, red-team controls.

Auth: any valid tenant API key, via X-API-Key header OR ?key= query param
(so the browser dashboard works without extensions).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from .. import config, metrics
from ..audit import get_audit_log
from ..detection.log_anomaly import LogAnomalyDetector
from ..gateway.auth import list_tenants, _load_tenants
from ..policy import get_policy_engine
from ..redteam import load_history, run_round

router = APIRouter(prefix="/api", tags=["dashboard"])


def _check_key(request: Request, key: str | None) -> None:
    candidates = _load_tenants()  # dict: api_key -> Tenant
    provided = key or request.headers.get("x-api-key", "")
    if provided not in candidates:
        raise HTTPException(status_code=401, detail="Provide a valid tenant API key (?key= or X-API-Key)")


@router.get("/metrics")
def api_metrics(key: str | None = Query(default=None), request: Request = None):
    _check_key(request, key)
    snap = metrics.snapshot()
    snap["audit_total"] = len(get_audit_log().query(limit=1000))
    return snap


@router.get("/audit")
def api_audit(limit: int = 50, tenant: str | None = None,
              key: str | None = Query(default=None), request: Request = None):
    _check_key(request, key)
    return {"rows": get_audit_log().query(limit=min(limit, 200), tenant=tenant)}


@router.get("/audit/verify")
def api_audit_verify(key: str | None = Query(default=None), request: Request = None):
    _check_key(request, key)
    return get_audit_log().verify()


@router.get("/policies")
def api_policies(key: str | None = Query(default=None), request: Request = None):
    _check_key(request, key)
    engine = get_policy_engine()
    out = {}
    for t in list_tenants():
        out[t["tenant"]] = engine._load_policy(t["tenant"])
    return out


@router.put("/policies/{tenant}")
async def api_put_policy(tenant: str, request: Request,
                         key: str | None = Query(default=None)):
    _check_key(request, key)
    try:
        data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {e}")
    try:
        path = get_policy_engine().save_policy(tenant, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"saved": str(path)}


@router.post("/redteam/run")
async def api_redteam_run(request: Request, n_attacks: int = 40,
                          key: str | None = Query(default=None)):
    _check_key(request, key)
    n = max(5, min(n_attacks, 300))
    summary = run_round(n_attacks=n, strategy="bandit", learn=True)
    return summary


@router.get("/redteam/history")
def api_redteam_history(limit: int = 20, key: str | None = Query(default=None),
                        request: Request = None):
    _check_key(request, key)
    return {"rounds": load_history(limit)}


@router.get("/tenants")
def api_tenants(key: str | None = Query(default=None), request: Request = None):
    _check_key(request, key)
    return {"tenants": list_tenants()}
