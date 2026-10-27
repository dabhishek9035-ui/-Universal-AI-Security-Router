from app.audit.audit_log import AuditLog


def test_append_and_verify_chain(tmp_path):
    log = AuditLog(db_path=tmp_path / "audit.db")
    for i in range(5):
        log.append(request_id=f"r{i}", tenant="default", input_type="prompt",
                   input_hash="a" * 64, decision="allow", reasons=[],
                   detections=[], router={"strategy": "rules"}, latency_ms=1.0)
    result = log.verify()
    assert result["ok"], result
    assert result["checked"] == 6  # genesis + 5


def test_tamper_detection(tmp_path):
    log = AuditLog(db_path=tmp_path / "audit.db")
    for i in range(3):
        log.append(request_id=f"r{i}", tenant="default", input_type="prompt",
                   input_hash="b" * 64, decision="block", reasons=["x"],
                   detections=[], router={}, latency_ms=2.0)

    # tamper directly in sqlite
    import sqlite3
    conn = sqlite3.connect(tmp_path / "audit.db")
    conn.execute("UPDATE audit SET decision='allow' WHERE request_id='r1'")
    conn.commit()
    conn.close()

    result = log.verify()
    assert not result["ok"]
    assert result["first_bad_id"] is not None


def test_query_filters_tenant(tmp_path):
    log = AuditLog(db_path=tmp_path / "audit.db")
    log.append(request_id="t1", tenant="acme", input_type="url", input_hash="c" * 64,
               decision="block", reasons=[], detections=[], router={}, latency_ms=1.0)
    log.append(request_id="t2", tenant="default", input_type="prompt",
               input_hash="d" * 64, decision="allow", reasons=[], detections=[],
               router={}, latency_ms=1.0)
    rows = log.query(limit=10, tenant="acme")
    assert len(rows) == 1
    assert rows[0]["request_id"] == "t1"
