from app.detection.phishing import PhishingDetector, url_features
from app.schemas import InputPayload


def det(text: str, input_type: str = "url"):
    return PhishingDetector().predict(InputPayload(text=text), input_type)


def test_features_extracted():
    f = url_features("http://paypa1-secure-login.verify-account.xyz/webscr?email=victim@mail.com")
    assert f["suspicious_tld"] == 1.0
    assert f["sensitive_path"] == 1.0
    assert f["no_https"] == 1.0


def test_phishing_url_flagged():
    d = det("http://paypa1-secure-login.verify-account.xyz/webscr?email=victim@mail.com")
    assert d.label == "phishing"
    assert d.score >= 0.5
    assert d.explanation != "no phishing indicators"


def test_ip_host_url_flagged():
    d = det("http://192.168.99.99/verify/login")
    assert d.label == "phishing"


def test_benign_url_clean():
    d = det("https://github.com/pytorch/pytorch")
    assert d.label == "benign"


def test_phishing_email_flagged():
    body = ("From: security@paypa1-verify.xyz\n"
            "URGENT: your account will be suspended immediately. "
            "verify your KYC now by clicking here: http://bad.example.xyz/login")
    d = det(body, input_type="email")
    assert d.label == "phishing"
