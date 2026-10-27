from app.detection.log_anomaly import LogAnomalyDetector, fit_baseline
from app.detection.type_detector import detect_type
from app.redteam import run_round
from app.schemas import InputPayload


def test_type_detection_rules():
    assert detect_type("https://example.com/page", "auto", {})[0] == "url"
    assert detect_type("From: a@b.com\nTo: c@d.com\nSubject: hi", "auto", {})[0] == "email"
    log = "2026-10-27 10:00:00 INFO app started\n2026-10-27 10:00:01 ERROR disk full"
    assert detect_type(log, "auto", {})[0] == "log"
    assert detect_type("hello there general", "auto", {})[0] == "prompt"
    assert detect_type("", "auto", {"filename": "invoice.pdf"})[0] == "file"


def test_log_anomaly_scores_unseen_template():
    det = LogAnomalyDetector()
    normal = InputPayload(text="2026-10-27 10:00:00 INFO request served in 12ms")
    d = det.predict(normal, "log")
    assert d.label == "benign"

    fit_baseline([
        "2026-10-27 10:00:00 INFO request served in 12ms",
        "2026-10-27 10:00:01 INFO request served in 9ms",
        "2026-10-27 10:00:02 INFO request served in 15ms",
    ])
    weird = InputPayload(text="2026-10-27 10:14:11 CRITICAL sshd[8811]: Unusual xr9zq2f1 template activity")
    d = det.predict(weird, "log")
    assert d.score > 0.4


def test_redteam_round_runs_and_records():
    summary = run_round(n_attacks=10, round_name="test-round", learn=False)
    assert summary["n_attacks"] >= 10
    assert 0.0 <= summary["asr_overall"] <= 1.0
    assert "injection" in summary["asr_by_category"] or "override" in summary["asr_by_category"]
