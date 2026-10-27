"""Phishing / malicious-URL detector.

Lexical + host-feature scoring (always on): entropy, IP hosts, punycode,
suspicious TLDs, shorteners, brand keywords on wrong domains, credential bait.
Optional trained stage: LogisticRegression over the same features from
scripts/train_phishing.py (models/phishing.joblib).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from .. import config
from .base import BaseDetector, Detection, sigmoid, shannon_entropy

SUSPICIOUS_TLDS = {
    "zip", "mov", "top", "xyz", "gq", "tk", "ml", "cf", "cn", "ru", "su",
    "click", "link", "work", "rest", "cam", "quest", "cyou", "sbs",
}
SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly",
    "cutt.ly", "rb.gy", "shorturl.at",
}
BRANDS = {
    "paypal", "apple", "microsoft", "office365", "outlook", "google", "amazon",
    "netflix", "facebook", "instagram", "whatsapp", "sbi", "hdfcbank",
    "icicibank", "axisbank", "chase", "wellsfargo", "dhl", "fedex",
}
BRAND_OFFICIAL_DOMAINS = {
    "paypal": ("paypal.com",),
    "apple": ("apple.com", "icloud.com"),
    "microsoft": ("microsoft.com", "office.com", "live.com"),
    "office365": ("office.com", "microsoft.com", "outlook.com"),
    "outlook": ("outlook.com", "microsoft.com", "live.com"),
    "google": ("google.com", "gmail.com"),
    "amazon": ("amazon.com",),
    "netflix": ("netflix.com",),
    "facebook": ("facebook.com",),
    "instagram": ("instagram.com",),
    "whatsapp": ("whatsapp.com",),
    "sbi": ("sbi.co.in", "onlinesbi.sbi"),
    "hdfcbank": ("hdfcbank.com",),
    "icicibank": ("icicibank.com",),
    "axisbank": ("axisbank.com",),
    "chase": ("chase.com",),
    "wellsfargo": ("wellsfargo.com",),
    "dhl": ("dhl.com",),
    "fedex": ("fedex.com",),
}
URGENT_WORDS = re.compile(
    r"\b(urgent|immediately|verify|suspend|suspended|unlock|limited|expire[sd]?|"
    r"confirm.your|alert|warning|winner|prize|refund|kyc|blocked|unusual\s+activity|"
    r"account\s+locked|click\s+here|act\s+now)\b", re.IGNORECASE)
IP_HOST_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
PUNYCODE_RE = re.compile(r"^xn--|[\u0080-\uffff]")
CRED_IN_URL_RE = re.compile(r"https?://[^/@\s]+:[^/@\s]+@")


def url_features(url: str) -> dict[str, float]:
    """Named lexical/host features, also used by the trainable model."""
    try:
        parsed = urlparse(url if "://" in url else "http://" + url)
    except ValueError:
        parsed = urlparse("")
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    full = url.lower()
    feats = {
        "url_len": min(len(url), 300) / 100.0,
        "host_len": min(len(host), 100) / 50.0,
        "num_dots": full.count("."),
        "num_hyphens": host.count("-"),
        "num_at": full.count("@"),
        "digit_ratio_host": (sum(c.isdigit() for c in host) / len(host)) if host else 0.0,
        "host_entropy": shannon_entropy(host),
        "path_entropy": shannon_entropy(path),
        "has_ip": 1.0 if IP_HOST_RE.match(host) else 0.0,
        "has_punycode": 1.0 if PUNYCODE_RE.search(host) else 0.0,
        "has_cred": 1.0 if CRED_IN_URL_RE.match(url) else 0.0,
        "is_shortener": 1.0 if host in SHORTENERS else 0.0,
        "suspicious_tld": 1.0 if host.rsplit(".", 1)[-1] in SUSPICIOUS_TLDS else 0.0,
        "no_https": 0.0 if parsed.scheme == "https" else 1.0,
        "many_subdomains": 1.0 if host.count(".") >= 4 else 0.0,
        "brand_keyword": 0.0,
        "brand_offdomain": 0.0,
        "sensitive_path": 1.0 if re.search(
            r"(login|verify|secure|account|update|wallet|confirm|webscr|billing)", path
        ) else 0.0,
    }
    for brand in BRANDS:
        if brand in full:
            feats["brand_keyword"] = 1.0
            official = BRAND_OFFICIAL_DOMAINS.get(brand, ())
            if official and not any(host == d or host.endswith("." + d) for d in official):
                feats["brand_offdomain"] = 1.0
            break
    return feats


_WEIGHTS: dict[str, float] = {
    "has_cred": 3.0, "has_ip": 2.5, "has_punycode": 2.0, "brand_offdomain": 2.5,
    "is_shortener": 1.2, "suspicious_tld": 1.2, "no_https": 0.8,
    "many_subdomains": 1.0, "num_at": 0.8, "sensitive_path": 0.8,
    "brand_keyword": 0.3, "num_hyphens": 0.25, "num_dots": 0.15,
    "host_entropy": 0.35, "path_entropy": 0.25, "url_len": 0.15,
    "host_len": 0.1, "digit_ratio_host": 0.8,
}


class PhishingDetector(BaseDetector):
    name = "phishing"
    input_types = ("url", "email", "prompt")
    cost = 0.8
    latency_ms = 3.0

    _model = None
    _model_loaded = False

    @classmethod
    def _load_model(cls):
        if not cls._model_loaded:
            cls._model_loaded = True
            try:
                import joblib
                path = config.MODELS_DIR / "phishing.joblib"
                if path.exists():
                    cls._model = joblib.load(path)
            except Exception:
                cls._model = None
        return cls._model

    def predict(self, payload, input_type: str) -> Detection:
        text = payload.text or ""
        urls = re.findall(r"https?://\S+|www\.\S+|\b[\w-]+\.(?:com|net|org|io|in|co)\b/\S*",
                          text, re.IGNORECASE)
        if not urls:
            if input_type == "url" and text.strip():
                urls = [text.strip()]
            else:
                # No URL present: URL features on prose are meaningless and the
                # trained model is out-of-distribution on them — never guess.
                return Detection(detector=self.name, label="benign", score=0.0,
                                 explanation="no URLs present to analyze")

        reasons: list[str] = []
        best_score = 0.0
        for url in urls[:5]:
            feats = url_features(url)
            raw = sum(_WEIGHTS[k] * v for k, v in feats.items())
            score = sigmoid(raw - 2.2)

            model = self._load_model()
            if model is not None:
                try:
                    import numpy as np
                    vec = np.array([[feats[k] for k in model.feature_names_]])
                    idx = list(model.classes_).index("phishing")
                    m_score = float(model.predict_proba(vec)[0][idx])
                    # max, not OR: lexical features are weak correlates (a
                    # benign github URL scores ~0.3 on heuristics alone), so
                    # two uncertain signals must not inflate each other; max
                    # still prevents an uncertain model from hiding strong
                    # heuristic evidence
                    score = max(score, m_score)
                except Exception:
                    pass

            if score > best_score:
                best_score = score
                reasons = [
                    f"{k}={v:g}" for k, v in feats.items()
                    if v and _WEIGHTS.get(k, 0) >= 1.0
                ][:5]

        # email-text signal on top of URL signal
        if input_type == "email":
            urgent = len(URGENT_WORDS.findall(text))
            if urgent >= 2:
                best_score = max(best_score, sigmoid(urgent - 1.5))
                reasons.append(f"{urgent} urgent/verify phrases in body")
            sender = (payload.meta or {}).get("from", "")
            if sender:
                from urllib.parse import urlparse as _up
                body_urls = re.findall(r"https?://([^/\s]+)", text)
                sender_domain = sender.rsplit("@", 1)[-1].lower().strip(">")
                for host in body_urls[:3]:
                    host = host.lower()
                    if sender_domain and not (host == sender_domain or host.endswith("." + sender_domain)):
                        best_score = max(best_score, 0.7)
                        reasons.append(f"link domain {host} != sender domain {sender_domain}")
                        break

        label = "phishing" if best_score >= 0.5 else "benign"
        return Detection(
            detector=self.name, label=label, score=min(best_score, 1.0),
            category="phishing" if label == "phishing" else None,
            explanation=("; ".join(reasons) if reasons else "no phishing indicators"),
        )
