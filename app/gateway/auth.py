"""API-key auth: X-API-Key -> tenant, from app/policy/tenants.yaml."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import yaml
from fastapi import Header, HTTPException

from .. import config


@dataclass
class Tenant:
    name: str
    policy: str


_cache: dict[str, Tenant] | None = None
_mtime: float = 0.0
_lock = threading.Lock()


def _load_tenants() -> dict[str, Tenant]:
    global _cache, _mtime
    path: Path = config.TENANTS_FILE
    mtime = path.stat().st_mtime if path.exists() else 0.0
    with _lock:
        if _cache is None or mtime != _mtime:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            _cache = {
                api_key: Tenant(name=name, policy=cfg.get("policy", "default"))
                for name, cfg in data.items()
                for api_key in [cfg.get("api_key")]
                if api_key
            }
            _mtime = mtime
        return _cache


def require_tenant(x_api_key: str = Header(default="")) -> Tenant:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    tenants = _load_tenants()
    tenant = tenants.get(x_api_key)
    if tenant is None:
        raise HTTPException(status_code=401, detail="Unknown API key")
    return tenant


def list_tenants() -> list[dict]:
    path = config.TENANTS_FILE
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [
        {"tenant": name, "policy": cfg.get("policy", "default")}
        for name, cfg in data.items()
    ]
