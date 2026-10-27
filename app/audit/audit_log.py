"""Hash-chained, tamper-evident audit log on SQLite."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from .. import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    request_id TEXT NOT NULL,
    tenant TEXT NOT NULL,
    input_type TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    decision TEXT NOT NULL,
    reasons TEXT NOT NULL,
    detections TEXT NOT NULL,
    router TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit(ts);
CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit(tenant);
"""


def canonical_row(row: dict) -> str:
    return json.dumps(row, sort_keys=True, separators=(",", ":"))


class AuditLog:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path or config.AUDIT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(_SCHEMA)
            row = conn.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO audit (ts, request_id, tenant, input_type, input_hash,"
                    " decision, reasons, detections, router, latency_ms, prev_hash, hash)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (time.time(), "genesis", "-", "-", "-" * 64, "-", "[]", "[]",
                     "{}", 0.0, "0" * 64, hashlib.sha256(b"genesis").hexdigest()),
                )

    def append(self, *, request_id: str, tenant: str, input_type: str,
               input_hash: str, decision: str, reasons: list[str],
               detections: list[dict], router: dict, latency_ms: float) -> str:
        with self._lock, self._connect() as conn:
            prev = conn.execute(
                "SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
            prev_hash = prev["hash"] if prev else "0" * 64
            row = {
                "ts": time.time(), "request_id": request_id, "tenant": tenant,
                "input_type": input_type, "input_hash": input_hash,
                "decision": decision, "reasons": reasons,
                "detections": detections, "router": router,
                "latency_ms": latency_ms, "prev_hash": prev_hash,
            }
            row_hash = hashlib.sha256(canonical_row(row).encode()).hexdigest()
            conn.execute(
                "INSERT INTO audit (ts, request_id, tenant, input_type, input_hash,"
                " decision, reasons, detections, router, latency_ms, prev_hash, hash)"
                " VALUES (:ts, :request_id, :tenant, :input_type, :input_hash,"
                " :decision, :reasons, :detections, :router, :latency_ms,"
                " :prev_hash, :hash)",
                {**row,
                 "reasons": json.dumps(reasons),
                 "detections": json.dumps(detections),
                 "router": json.dumps(router),
                 "hash": row_hash},
            )
        return row_hash

    def query(self, limit: int = 50, tenant: str | None = None) -> list[dict]:
        q = "SELECT * FROM audit WHERE request_id != 'genesis'"
        params: list = []
        if tenant:
            q += " AND tenant = ?"
            params.append(tenant)
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._lock, self._connect() as conn:
            rows = conn.execute(q, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["reasons"] = json.loads(d["reasons"])
            d["detections"] = json.loads(d["detections"])
            d["router"] = json.loads(d["router"])
            out.append(d)
        return out

    def verify(self) -> dict:
        """Walk the chain; return {ok, checked, first_bad_id}."""
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM audit ORDER BY id ASC").fetchall()
        prev_hash = "0" * 64
        for i, r in enumerate(rows):
            if i == 0:
                # genesis row anchors the chain; its own hash is a fixed seed
                prev_hash = r["hash"]
                continue
            if r["prev_hash"] != prev_hash:
                return {"ok": False, "checked": i, "first_bad_id": r["id"],
                        "issue": "broken chain link"}
            row = {
                "ts": r["ts"], "request_id": r["request_id"], "tenant": r["tenant"],
                "input_type": r["input_type"], "input_hash": r["input_hash"],
                "decision": r["decision"], "reasons": json.loads(r["reasons"]),
                "detections": json.loads(r["detections"]), "router": json.loads(r["router"]),
                "latency_ms": r["latency_ms"], "prev_hash": r["prev_hash"],
            }
            if hashlib.sha256(canonical_row(row).encode()).hexdigest() != r["hash"]:
                return {"ok": False, "checked": i + 1, "first_bad_id": r["id"],
                        "issue": "row hash mismatch (row was tampered)"}
            prev_hash = r["hash"]
        return {"ok": True, "checked": len(rows), "first_bad_id": None}


_log: AuditLog | None = None


def get_audit_log() -> AuditLog:
    global _log
    if _log is None:
        _log = AuditLog()
    return _log
