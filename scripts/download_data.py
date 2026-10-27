"""Download REAL datasets for training (no API keys needed).

Injection  (HuggingFace datasets-server /rows JSON API, anonymous):
  - xTRam1/safe-guard-prompt-injection      ~10.3k  (label 1 = injection)
  - 3nesdeniz/agentic-prompt-injection-5k   ~4.9k   (rich: attack_family, language)
  - deepset/prompt-injections               ~526    (the dataset in PROJECT_SUMMARY)
  - rikka-snow/prompt-injection-multilingual ~7.3k  (de/es/pt/...)
Phishing (live public feeds):
  - OpenPhish free feed                     live phishing URLs
  - Tranco top-1M + Majestic Million        benign domains (sampled)
Curated benign (handwritten, marked source=curated):
  - short greetings + PII-bearing benign texts, so the injection model learns
    that PII/greetings alone are NOT injection (that's the DLP detector's job)

Output: data/real/injection.jsonl, data/real/phishing.jsonl
Run:    python scripts/download_data.py
"""
from __future__ import annotations

import csv
import io
import json
import random
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config  # noqa: E402

HF_ROWS = "https://datasets-server.huggingface.co/rows"
PAGE = 100

INJECTION_SOURCES = [
    # (hf dataset id, split, text field, label field, malicious label value)
    ("xTRam1/safe-guard-prompt-injection", "train", "text", "label", 1),
    ("xTRam1/safe-guard-prompt-injection", "test", "text", "label", 1),
    ("3nesdeniz/agentic-prompt-injection-5k", "train", "text", "label", 1),
    ("3nesdeniz/agentic-prompt-injection-5k", "test", "text", "label", 1),
    ("3nesdeniz/agentic-prompt-injection-5k", "validation", "text", "label", 1),
    ("deepset/prompt-injections", "train", "text", "label", 1),
    ("rikka-snow/prompt-injection-multilingual", "train", "text", "label", 1),
    ("rikka-snow/prompt-injection-multilingual", "test", "text", "label", 1),
]

CURATED_BENIGN = [
    "hi", "Hi", "HI", "hello", "hey there", "good morning", "good night",
    "thanks", "thank you!", "ok", "cool", "nice", "yes", "no", "maybe",
    "what's up?", "how are you?", "can you help me?", "ನಮಸ್ಕಾರ", "ಧನ್ಯವಾದಗಳು",
    "hola", "olá", "danke", "merci", "namaste",
    "Please update my billing email to jane.doe@example.com.",
    "My card 4111 1111 1111 1111 was charged twice this month, help.",
    "Reminder: send the invoice to accounts@corp.example by Friday.",
    "Customer support: my phone number changed to +91 9876543210.",
    "My aadhaar 4821 9034 7765 needs updating in the college portal.",
    "Use AWS key AKIAIOSFODNN7EXAMPLE for the nightly batch job.",
    "My SSN is 512-88-3017, please verify my identity.",
]

BENIGN_PATHS = ["", "", "", "", "about", "contact", "blog", "products",
                "services", "careers", "support", "docs", "news", "login"]
NUM_BENIGN_URLS = 12000


def fetch_split(client: httpx.Client, dataset: str, split: str,
                text_field: str, label_field: str, mal_value) -> list[dict]:
    """Page through the datasets-server /rows endpoint (100 rows/call)."""
    rows: list[dict] = []
    offset = 0
    quoted = dataset.replace("/", "%2F")
    while True:
        url = f"{HF_ROWS}?dataset={quoted}&config=default&split={split}&offset={offset}&length={PAGE}"
        for attempt in range(8):
            try:
                resp = client.get(url, timeout=30)
                resp.raise_for_status()
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < 7:
                    wait = float(e.response.headers.get("retry-after") or 0)
                    wait = max(wait, 5 * (attempt + 1))
                    time.sleep(min(wait, 45))
                    continue
                raise
            except httpx.HTTPError:
                if attempt == 7:
                    raise
                time.sleep(2 * (attempt + 1))
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"{dataset}/{split}: {data['error']}")
        batch = data.get("rows", [])
        if not batch:
            break
        for item in batch:
            row = item["row"]
            text = str(row.get(text_field, "")).strip()
            label = row.get(label_field)
            if not text:
                continue
            rows.append({
                "text": text,
                "label": "malicious" if label == mal_value else "benign",
                "source": f"hf:{dataset}:{split}",
                "category": row.get("attack_family") or row.get("technique"),
                "language": row.get("language"),
            })
        offset += len(batch)
        time.sleep(0.3)
        if len(batch) < PAGE:
            break
    print(f"  {dataset}/{split}: {len(rows)} rows")
    return rows


def download_injection(client: httpx.Client) -> list[dict]:
    all_rows: list[dict] = []
    jobs = [(client, ds, split, tf, lf, mv)
            for ds, split, tf, lf, mv in INJECTION_SOURCES]
    with ThreadPoolExecutor(max_workers=2) as ex:
        for result in ex.map(lambda a: fetch_split(*a), jobs):
            all_rows.extend(result)

    for text in CURATED_BENIGN:
        all_rows.append({"text": text, "label": "benign", "source": "curated",
                         "category": None, "language": None})

    # dedupe on normalized text
    seen: set[str] = set()
    unique: list[dict] = []
    for r in all_rows:
        key = " ".join(r["text"].lower().split())
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def download_phishing_hf() -> list[dict]:
    """Balanced sample from flwrlabs/fed-phishing-urls (~1.1M real URLs).

    label 0 = benign, 1 = phishing. Sampled instead of full download; benign
    rows include deep realistic paths, not just top-domain homepages.
    """
    import pandas as pd

    parquet_url = ("https://huggingface.co/api/datasets/"
                   "flwrlabs/fed-phishing-urls/parquet/default/train/0.parquet")
    cache = config.DATA_DIR / "real" / "_fed_phishing_train.parquet"
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        with httpx.Client(follow_redirects=True, timeout=300) as client:
            with client.stream("GET", parquet_url) as resp:
                resp.raise_for_status()
                with open(cache, "wb") as f:
                    for chunk in resp.iter_bytes(1 << 20):
                        f.write(chunk)
    df = pd.read_parquet(cache, columns=["url", "label"])
    rng = random.Random(42)
    rows: list[dict] = []
    for label, n_want in ((1, 25000), (0, 25000)):
        sub = df[df.label == label]
        take = min(n_want, len(sub))
        idx = rng.sample(range(len(sub)), take)
        sub = sub.iloc[idx]
        for u in sub["url"]:
            u = str(u).strip()
            if not u or len(u) < 4:
                continue
            if not u.lower().startswith(("http://", "https://")):
                u = "http://" + u
            rows.append({"url": u, "label": "phishing" if label == 1 else "benign",
                         "source": "hf:fed-phishing-urls"})
    print(f"hf:fed-phishing-urls: sampled {len(rows)} (25k phishing + 25k benign target)")
    return rows


def download_phishing() -> list[dict]:
    rows: list[dict] = download_phishing_hf()
    with httpx.Client(follow_redirects=True, timeout=60) as client:
        # live phishing URLs (today's active feed)
        resp = client.get("https://openphish.com/feed.txt")
        resp.raise_for_status()
        phish = [ln.strip() for ln in resp.text.splitlines() if ln.strip().startswith("http")]
        for url in phish:
            rows.append({"url": url, "label": "phishing", "source": "openphish"})
        print(f"openphish: {len(phish)} phishing urls")

        # benign top-domain homepages (easy negatives; keep for domain coverage)
        resp = client.get("https://tranco-list.eu/top-1m.csv.zip")
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            name = z.namelist()[0]
            with z.open(name) as f:
                text = f.read().decode("utf-8", errors="ignore")
        tranco = [ln.split(",")[1].strip() for ln in text.splitlines()
                  if "," in ln][:500_000]
        print(f"tranco: {len(tranco)} domains")

    # majestic million as second benign source
    majestic: list[str] = []
    try:
        with httpx.Client(follow_redirects=True, timeout=60) as client:
            resp = client.get("http://downloads.majestic.com/majestic_million.csv")
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            majestic = [r["Domain"] for r in reader if r.get("Domain")][:200_000]
        print(f"majestic: {len(majestic)} domains")
    except Exception as e:
        print(f"majestic skipped: {e}")

    rng = random.Random(42)
    domains = tranco[: len(tranco) // 2] + majestic[: len(majestic) // 2]
    rng.shuffle(domains)
    n = min(8000, len(domains))
    for d in domains[:n]:
        d = d.strip().strip(".")
        path = rng.choice(BENIGN_PATHS)
        scheme = "https" if rng.random() < 0.85 else "http"
        url = f"{scheme}://{d}/{path}".rstrip("/") + ("/" if not path else "")
        rows.append({"url": url, "label": "benign", "source": "tranco+majestic"})

    seen: set[str] = set()
    unique: list[dict] = []
    for r in rows:
        key = r["url"].strip().lower().rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    config.ensure_dirs()
    out_real = config.DATA_DIR / "real"
    out_real.mkdir(exist_ok=True)

    only = sys.argv[1] if len(sys.argv) > 1 else "all"

    if only in ("all", "injection"):
        print("downloading injection datasets from huggingface...")
        with httpx.Client() as client:
            inj = download_injection(client)
        mal = sum(1 for r in inj if r["label"] == "malicious")
        print(f"injection: {len(inj)} rows ({mal} malicious / {len(inj) - mal} benign)")
        by_src: dict[str, int] = {}
        for r in inj:
            src = r["source"].split(":")[-2] if r["source"].startswith("hf:") else r["source"]
            by_src[src] = by_src.get(src, 0) + 1
        for src, n in sorted(by_src.items(), key=lambda kv: -kv[1]):
            print(f"  {src}: {n}")
        write_jsonl(out_real / "injection.jsonl", inj)

    if only in ("all", "phishing"):
        print("downloading phishing feeds...")
        phish = download_phishing()
        n_phish = sum(1 for r in phish if r["label"] == "phishing")
        print(f"phishing: {len(phish)} rows ({n_phish} phishing / {len(phish) - n_phish} benign)")
        write_jsonl(out_real / "phishing.jsonl", phish)

    print(f"\nsaved to {out_real}")


if __name__ == "__main__":
    main()
