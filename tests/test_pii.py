from app.detection.pii_dlp import PIIDetector, redact_text
from app.schemas import InputPayload


def det(text: str):
    return PIIDetector().predict(InputPayload(text=text), "prompt")


def test_detects_email_and_card_and_aadhaar():
    text = "Contact jane.doe@example.com, card 4111 1111 1111 1111, aadhaar 4821 9034 7765"
    d = det(text)
    assert d.label == "pii"
    types = {s["type"] for s in d.spans}
    assert "email" in types
    assert "credit_card" in types
    assert "aadhaar_like" in types
    assert d.score >= 0.6


def test_detects_aws_key_and_jwt():
    d = det("use key AKIAIOSFODNN7EXAMPLE or eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjMifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJVadQssw5c")
    types = {s["type"] for s in d.spans}
    assert "aws_access_key" in types
    assert "jwt" in types
    assert d.score == 1.0


def test_luhn_rejects_random_digits():
    d = det("order number 1234567812345678 shipped")
    types = {s["type"] for s in d.spans}
    assert "credit_card" not in types


def test_benign_text_is_clean():
    d = det("Please summarize this article about renewable energy in three bullets.")
    assert d.label == "benign"
    assert d.spans == []


def test_redaction_replaces_spans():
    text = "email me at jane.doe@example.com please"
    d = det(text)
    out = redact_text(text, d.spans)
    assert "jane.doe@example.com" not in out
    assert "[REDACTED:email]" in out
    assert out.startswith("email me at ") and out.endswith(" please")
