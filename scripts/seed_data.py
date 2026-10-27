"""Generate synthetic labeled datasets into data/train/ (no external deps).

Datasets:
  injection.jsonl  {"text", "label": malicious|benign, "category"}
  phishing.jsonl   {"url", "label": phishing|benign}
  pii.jsonl        {"text", "spans": [{start,end,type}]} for NER-style checks
  llm_prompts.jsonl {"text", "difficulty": easy|hard} seeds for the LLM router
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.redteam.attacks import BENIGN_SAMPLES, SEED_ATTACKS, generate_attacks  # noqa: E402

from app import config  # noqa: E402

PHISH_URLS = [
    "http://paypa1-secure-login.verify-account.xyz/webscr?email={u}",
    "http://192.168.{a}.{b}/verify/login?redirect=account",
    "https://{brand}.com.account-verify{tld}/session/confirm?id={n}",
    "http://secure-{brand}.{tld}/update-kyc?token={hex}",
    "http://appleid.apple.verify-unlock.{tld}/signin",
    "http://bit.ly/{n}{hex}",
    "https://{brand}.wallet-recovery.{tld}/import-seed",
]
BENIGN_URLS = [
    "https://www.wikipedia.org/wiki/Machine_learning",
    "https://github.com/pytorch/pytorch",
    "https://docs.python.org/3/library/asyncio.html",
    "https://www.kaggle.com/datasets",
    "https://news.ycombinator.com/item?id=38123456",
    "https://developer.mozilla.org/en-US/docs/Web/HTTP",
    "https://arxiv.org/abs/2401.04088",
    "https://www.india.gov.in",
]

FIRST = ["Aarav", "Diya", "John", "Priya", "Marco", "Sara", "Wei", "Emma", "Rahul", "Lena"]
LAST = ["Sharma", "Patel", "Smith", "Rao", "Klein", "Johnson", "Chen", "Garcia", "Iyer", "Muller"]
DOMAINS = ["example.com", "corp.example", "mail.example.org", "university.edu"]


def gen_pii(n: int, rng: random.Random) -> list[dict]:
    rows = []
    templates = [
        "Contact {first} {last} at {email} or {phone} regarding the invoice.",
        "Customer {first} {last}, card 4111 1111 1111 1111, aadhaar {aadhaar}.",
        "Escalate to {email}; SSN {ssn}; backup password: {pw}",
        "AWS key for the batch job: AKIAIOSFODNN7EXAMPLE (rotate after use).",
        "Ticket filed by {first} {last} <{email}> from IP 10.0.{a}.{b}.",
    ]
    for _ in range(n):
        t = rng.choice(templates)
        text = t.format(
            first=rng.choice(FIRST), last=rng.choice(LAST),
            email=f"{rng.choice(FIRST).lower()}.{rng.choice(LAST).lower()}@{rng.choice(DOMAINS)}",
            phone=f"+91 {rng.randint(70000, 99999)}{rng.randint(10000, 99999)}",
            aadhaar=f"{rng.randint(1000, 9999)} {rng.randint(1000, 9999)} {rng.randint(1000, 9999)}",
            ssn=f"{rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(1000, 9999)}",
            pw=f"pw-{rng.randint(100000, 999999)}",
            a=rng.randint(0, 255), b=rng.randint(0, 255),
        )
        rows.append({"text": text})
    return rows


def main() -> None:
    config.ensure_dirs()
    out_dir = config.DATA_DIR / "train"
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7)

    # --- injection: mutate seeds as malicious, benign pool expanded by paraphrases ---
    # Only injection-family categories belong here: PII-exfil and phishing samples
    # are handled by their own detectors and must not teach the injection model
    # that "a prompt containing a credit card" == injection (that's a DLP job).
    INJECTION_CATEGORIES = {"override", "jailbreak", "fake_system", "exfil",
                            "role_switch", "tool_abuse", "encoding", "injection"}
    inj_rows = []
    for atk in generate_attacks(400):
        if atk.category == "benign":
            inj_rows.append({"text": atk.text, "label": "benign", "category": "chitchat"})
        elif atk.category in INJECTION_CATEGORIES:
            inj_rows.append({"text": atk.text, "label": "malicious", "category": atk.category})
        # pii_exfil / phishing attacks are skipped here on purpose
    for b in BENIGN_SAMPLES:
        for suffix in ["", " Can you also make it shorter?", " Thanks!", " (for my homework)"]:
            inj_rows.append({"text": b + suffix, "label": "benign", "category": "chitchat"})
    # PII-bearing but non-injection texts: the DLP detector owns these, the
    # injection model must treat them as benign.
    PII_BENIGN = [
        "Please update my billing email to jane.doe@example.com.",
        "My card 4111 1111 1111 1111 was charged twice this month, help.",
        "Reminder: send the invoice to accounts@corp.example by Friday.",
        "Customer support: my phone number changed to +91 9876543210.",
        "My aadhaar 4821 9034 7765 needs updating in the college portal.",
        "Use AWS key AKIAIOSFODNN7EXAMPLE for the nightly batch job.",
    ]
    for b in PII_BENIGN:
        inj_rows.append({"text": b, "label": "benign", "category": "contains_pii"})
        inj_rows.append({"text": b + " Thanks for the help!", "label": "benign", "category": "contains_pii"})
    rng.shuffle(inj_rows)
    with open(out_dir / "injection.jsonl", "w", encoding="utf-8") as f:
        for r in inj_rows:
            f.write(json.dumps(r) + "\n")

    # --- phishing urls ---
    phish_rows = []
    tlds = ["xyz", "top", "info", "click", "cyou", "zip"]
    brands = ["paypal", "apple", "microsoft", "sbi", "netflix", "amazon"]
    for i in range(300):
        url = rng.choice(PHISH_URLS).format(
            u=f"victim{i}@mail.com", a=rng.randint(1, 254), b=rng.randint(1, 254),
            brand=rng.choice(brands), tld=rng.choice(tlds),
            n=rng.randint(10000, 99999), hex=f"{rng.getrandbits(32):08x}")
        phish_rows.append({"url": url, "label": "phishing"})
    for i in range(300):
        url = rng.choice(BENIGN_URLS)
        if "?" in url:
            url += f"&ref={rng.randint(1, 999)}"
        phish_rows.append({"url": url, "label": "benign"})
    rng.shuffle(phish_rows)
    with open(out_dir / "phishing.jsonl", "w", encoding="utf-8") as f:
        for r in phish_rows:
            f.write(json.dumps(r) + "\n")

    # --- pii with spans (written after computing spans via the detector's regexes) ---
    from app.detection.pii_dlp import _PATTERNS
    pii_rows = []
    for row in gen_pii(300, rng):
        text = row["text"]
        spans = []
        for regex, pii_type, sens in _PATTERNS:
            for m in regex.finditer(text):
                spans.append({"start": m.start(), "end": m.end(), "type": pii_type})
        pii_rows.append({"text": text, "spans": spans})
    with open(out_dir / "pii.jsonl", "w", encoding="utf-8") as f:
        for r in pii_rows:
            f.write(json.dumps(r) + "\n")

    # --- llm router seeds ---
    easy = [
        "hi", "thanks!", "what does 'idk' mean?", "rephrase this sentence politely: send it now",
        "translate 'good night' to kannada", "fix the typo in: recieve", "ok",
        "summarize this in one line: The cat sat on the mat and slept.",
    ]
    hard = [
        "Design a rate limiter for a multi-tenant API and justify the trade-offs.",
        "Debug why my asyncio task deadlocks when the executor pool is saturated.",
        "Prove that the halting problem is undecidable, step by step.",
        "Compare LSTM vs transformer architectures for log anomaly detection, then recommend one for 6GB VRAM.",
        "Write a SQL migration plan to shard a 2TB table with zero downtime.",
        "Derive the gradient of the softmax cross-entropy loss and explain each term.",
    ]
    with open(out_dir / "llm_prompts.jsonl", "w", encoding="utf-8") as f:
        for i in range(400):
            if rng.random() < 0.5:
                text = rng.choice(easy)
                if rng.random() < 0.4:
                    text += f" ({rng.choice(['quick one', 'simple q', 'just curious'])})"
                f.write(json.dumps({"text": text, "difficulty": "easy"}) + "\n")
            else:
                text = rng.choice(hard)
                if rng.random() < 0.4:
                    text += " " + rng.choice(["Think step by step.", "Be thorough.", "Then analyze the results."])
                f.write(json.dumps({"text": text, "difficulty": "hard"}) + "\n")

    print(f"wrote datasets to {out_dir}")
    print(f"  injection.jsonl: {len(inj_rows)} rows")
    print(f"  phishing.jsonl:  {len(phish_rows)} rows")
    print(f"  pii.jsonl:       {len(pii_rows)} rows")
    print(f"  llm_prompts.jsonl: 400 rows")


if __name__ == "__main__":
    main()
