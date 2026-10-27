# Universal AI Security Router

One plug-and-play **security gateway in front of any app or LLM**. Any input goes in —
prompt, email, URL, log, file, network flow. A **learned router** decides which
specialist detector(s) inspect it, a **policy engine** decides what happens
(allow / block / redact / flag / escalate), and clean LLM requests are routed to the
**cheapest capable model** (local 4-bit Ollama vs paid API). A **red-team loop**
continuously attacks the system and retrains it.

Everything in this repo runs locally on modest hardware with real trained models and real datasets.

> Full project rationale, datasets table, methodology and evaluation plan:
> [docs/PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md) ·
> code-to-design map: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Repository layout

```
ai_router/
├── app/                  FastAPI gateway (backend)
│   ├── main.py           endpoints, CORS, lifespan
│   ├── pipeline.py       the request path: detect → route → policy → audit → LLM
│   ├── detection/        input-type detector + 5 specialist detectors + output guard
│   ├── router/           LinUCB bandit, security router, LLM difficulty router
│   ├── policy/           per-tenant policy engine + YAML files + tenants
│   ├── audit/            SHA-256 hash-chained audit log (SQLite)
│   ├── llm/              Ollama + OpenAI-compatible providers
│   ├── redteam/          attack generator + closed-loop runner
│   ├── gateway/          API-key auth + rate limiting
│   ├── dashboard/        legacy zero-build dashboard (still served at :8000)
│   └── metrics.py        in-process counters for the live dashboard
├── frontend/             Next.js 14 + TypeScript + R3F dashboard (the main UI)
├── scripts/              download_data.py, train_*.py, redteam_run.py, seed_data.py
├── data/                 real/ + train/ datasets, audit.db, bandit state, learned patterns
├── models/               trained models + eval provenance JSONs
├── docs/                 PROJECT_SUMMARY.md (the design doc), ARCHITECTURE.md
└── tests/                41 pytest cases
```

---

## Quickstart

```bash
# 1) backend
cd ai_router
python -m venv .venv
.venv\Scripts\activate               # Windows (source .venv/bin/activate elsewhere)
pip install -r requirements.txt
python run.py                        # gateway + legacy dashboard on http://127.0.0.1:8000

# 2) frontend (second terminal)
cd ai_router/frontend
npm install
npm run dev                          # main UI on http://localhost:3000
```

Dev API keys live in `app/policy/tenants.yaml`: `dev-default-key`, `dev-acme-key`.
The frontend ships with `dev-default-key` prefilled (editable in the Console section).

### What to click (60-second tour)

1. **Live scan console** — type anything or use the example chips. The decision panel
   shows the policy outcome, every detector's score and the router's reasoning
   ("blocked because prompt_injection score 0.97 > 0.85").
2. **Guarded LLM chat** — send a prompt. Watch the router pick **LOCAL MODEL (free)**
   vs **BIG MODEL (paid API)** from a difficulty estimate, see the model name, the
   difficulty meter, and the output guard's scan of the answer.
3. **Metrics strip** — requests / blocked / redacted / latency / cost saved update
   every 5s; the 3D orb behind the page heats up as the blocked share rises.
4. **Audit log** — every decision is a row in a tamper-evident hash chain; the pill
   shows "chain verified · N rows".
5. **Red team** — run an adversarial round; watch the attack success rate drop across
   rounds as the loop learns from its misses.

---

## How the LLM routing works — and where "cost saved" comes from

This is the part of the dashboard that only moves when you use the **Guarded LLM Chat**
panel (or call `POST /v1/chat` yourself). Scanning alone never touches an LLM.

### The routing decision

For every chat request the gateway:

1. **Scans the input** (same pipeline as `/v1/scan`). Blocked inputs never reach any model.
2. **Estimates difficulty** from cheap features — length, reasoning cues ("step by step",
   "prove", "derive"), code cues, math cues, easy cues ("hi", "translate this") — blended
   with a trainable logistic model when present (`models/llm_router.joblib`).
3. **Picks a tier:**
   - difficulty **< 0.5 → local tier**: Ollama running a quantized model on your GPU
     (default `gemma3:4b`, free, private, ~10-50ms/token on an RTX 4050).
   - difficulty **≥ 0.5 → big tier**: any OpenAI-compatible API (`OPENAI_BASE_URL`,
     `BIG_MODEL`).
4. **Escalates on failure**: if the local model is unreachable or errors, the request is
   retried once on the big tier automatically.
5. **Guards the output**: the answer is re-scanned — leaked PII is redacted in place,
   echoed injection content is flagged (shown, not hidden).

You can bypass the router with `"force_tier": "local" | "big"` in the request body —
useful for demos and for measuring the cost difference directly.

### The math behind the "Cost saved" card

```
per chat call:  cost ≈ tokens_per_response / 1000 × cost_per_1k_tokens
usd_actual       = big_calls × COST_BIG_PER_1K × AVG_RESPONSE_TOKENS/1000
                 + local_calls × COST_LOCAL_PER_1K × AVG_RESPONSE_TOKENS/1000
usd_if_always_big = (big_calls + local_calls) × COST_BIG_PER_1K × AVG_RESPONSE_TOKENS/1000
usd_saved        = usd_if_always_big − usd_actual
est_savings_pct  = 100 × (1 − usd_actual / usd_if_always_big)
```

Defaults (override via `.env`): `COST_BIG_PER_1K=0.15`, `COST_LOCAL_PER_1K=0.0`,
`AVG_RESPONSE_TOKENS=400`. So **every prompt routed to the local model instead of the
big API saves ~$0.06** at the default estimate, and the savings % is just the local
share of calls. These are *estimates* from configurable constants, not measured billing
— that's why the card is labelled "est".

### Why your counters were at 0

| Counter | Updated by | Was 0 because |
|---|---|---|
| Cost saved / savings % | `/v1/chat` calls only | The chat panel didn't exist yet and only `/v1/scan` had been used |
| Local / big call counts | every routed chat call | Same — plus the default `LOCAL_MODEL` (`qwen2.5:3b`) wasn't installed, so local calls would have failed anyway |
| "model routed" badge in Chat | each chat response | Appears only after you send a prompt |

**Fixed now:** the default `LOCAL_MODEL` is `gemma3:4b` (verified present in your local
Ollama), the frontend has a Guarded Chat panel, and the Cost-saved card shows the
local/big call split. Send one prompt in the Chat section and the card reads
`$0.0600 saved · 100% vs always-big · 1 local / 0 big calls`.

### Setting up the two tiers

**Local (already working on this machine):** [Ollama](https://ollama.com) on
`http://127.0.0.1:11434`, model `gemma3:4b` (`ollama pull gemma3:4b` if missing).
Change with `LOCAL_MODEL` in `.env`. First call after a gateway restart loads the
model into VRAM (~13s once); later calls are fast.

**Big (optional):** copy `.env.example` → `.env` and set
`OPENAI_API_KEY=sk-...` (+ optionally `OPENAI_BASE_URL` for Azure/OpenRouter/Together,
`BIG_MODEL=gpt-4o-mini`). Without a key, big-tier requests return an honest
"unconfigured" status — never a silently unguarded answer.

---

## The request path

```
Client → [API-key auth + rate limit] → Input Type Detector → Learned Router (LinUCB)
      → Specialist Detectors (parallel) → Policy Engine → allow/redact/block/flag/escalate
      → (chat) LLM Router → local Ollama or big API → Output Guard → hash-chained Audit Log

Side loop: Red-Team attacks → misses → hard-example buffer → learned patterns
           + bandit rewards → re-measure ASR
```

## Components (where to look)

| Component | Code | Notes |
|---|---|---|
| Input Type Detector | `app/detection/type_detector.py` | rules (URL/email-header/log-format/file/flow) + optional trained classifier |
| Prompt injection | `app/detection/prompt_injection.py` | 25+ weighted pattern families incl. Kannada/Hindi/Chinese/es/pt/de/fr, base64 decoding, confusable-unicode detection, real-data TF-IDF+LR blend |
| PII / secrets (DLP) | `app/detection/pii_dlp.py` | Luhn, AWS/GitHub/OpenAI/Slack/JWT patterns, exact spans for redaction |
| Phishing / malicious URL | `app/detection/phishing.py` | entropy, punycode, IP hosts, brand-off-domain, sender/link mismatch; real-data LR blend |
| Log / network anomaly | `app/detection/log_anomaly.py` | template-mining z-scores, flow-feature z-scores, optional IsolationForest |
| Malware (static only) | `app/detection/malware.py` | byte entropy, extension risk, packer/import hints — **never executes samples** |
| Learned Router | `app/router/security_router.py`, `bandit.py` | LinUCB; arms = detector subsets; reward = correctness − λ₁cost − λ₂latency; strategies bandit/rules/all kept as baselines |
| LLM Router | `app/router/llm_router.py` | difficulty features → local vs big; escalation on local failure |
| Policy Engine | `app/policy/engine.py` | per-tenant YAML, hot-reload, precedence block > escalate > redact > flag > allow, human-readable reasons |
| Audit + Explainability | `app/audit/audit_log.py` | SHA-256 hash chain on SQLite; `verify()` detects tampering |
| Red-Team loop | `app/redteam/` | 7 mutation families, ASR per category, hard-example buffer, learned patterns (weight-upgrading) |
| Output Guard | `app/detection/output_guard.py` | re-scans model answers; redacts leaks, flags echoed injections |
| Metrics | `app/metrics.py` | request/decision/latency/LLM-tier counters, cost-saved math |

## API reference

| Endpoint | What it does |
|---|---|
| `POST /v1/scan` | Scan any input → decision, detections, redacted text |
| `POST /v1/chat` | Guarded completion: scan → route (local/big) → generate → output guard. Body: `{"text", "system"?, "force_tier"?: "local"\|"big"}` |
| `POST /v1/feedback` | `{"request_id","actual":"malicious"\|\"benign\"}` → online bandit reward |
| `GET /healthz` | Health + audit-chain integrity |
| `GET /api/metrics` | KPIs, latency percentiles, LLM tier counts, cost-saved estimate |
| `GET /api/audit?limit=50` · `GET /api/audit/verify` | Audit feed · hash-chain walk |
| `GET /api/policies` · `PUT /api/policies/{tenant}` | View / edit tenant policy (hot-reloaded) |
| `POST /api/redteam/run?n_attacks=40` · `GET /api/redteam/history` | Run a round · ASR history |

All `/v1/*` need `X-API-Key`. `/api/*` accepts `X-API-Key` or `?key=` (browser-friendly).

Example:

```bash
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H "X-API-Key: dev-default-key" -H "Content-Type: application/json" \
  -d '{"text":"Explain TCP vs UDP in one paragraph.","force_tier":"local"}'
```

## Training pipelines (real data)

```bash
python scripts/download_data.py             # pulls REAL data -> data/real/ (no API keys)
python scripts/train_injection.py           # -> models/injection.joblib + injection_eval.json
python scripts/train_phishing.py            # -> models/phishing.joblib   + phishing_eval.json
python scripts/train_llm_router.py          # -> models/llm_router.joblib
python scripts/redteam_run.py --rounds 3 --n 60 --benchmark
```

| Purpose | Source | Rows |
|---|---|---|
| Prompt injection | HF `xTRam1/safe-guard-prompt-injection` | 10,135 |
| Prompt injection (multilingual) | HF `rikka-snow/prompt-injection-multilingual` | 6,040 |
| Prompt injection (agentic, technique labels) | HF `3nesdeniz/agentic-prompt-injection-5k` | 4,935 |
| Prompt injection | HF `deepset/prompt-injections` | 542 |
| Phishing URLs (real, balanced) | HF `flwrlabs/fed-phishing-urls` (1.1M, sampled) | 49,893 |
| Phishing URLs (live) | OpenPhish public feed | ~300/day |
| Benign domains | Tranco top-1M + Majestic Million | 8k |

- Injection: **21,682 rows (8,567 attacks)**, held-out **macro F1 0.977, ROC-AUC 0.996**
- Phishing: **58,181 rows (25,220 phishing)**, held-out **macro F1 0.772, ROC-AUC 0.849**
  — real URLs are hard for lexical features; char-CNN/transformer is the upgrade path
- Provenance + metrics stored in `models/*_eval.json`
- Detector models blend with heuristics via noisy-OR (injection) / max (phishing);
  out-of-distribution guards skip the model for very short inputs, non-Latin scripts,
  and texts without URLs
- `seed_data.py` + `data/train/` remain as synthetic fallback/tests fixtures

### Red-team loop (measured on the real-data models)

Mutated attacks (base64, leetspeak, document-wrapping, paraphrase, Kannada) start at
**ASR 30.6%**; the closed loop drives it to **6.9% in 2 rounds with 0 false positives
on benign control traffic**. Learned patterns persist in `data/learned_patterns.json`
and hot-reload into the detector.

## Frontend

`frontend/` — Next.js 14 App Router, TypeScript strict, React Three Fiber. One
persistent WebGL canvas behind the whole app (glass UI, 7 themes, quality tiers,
reduced-motion support). The 3D orb encodes exactly one live value — the blocked share
of traffic — easing toward it every frame; the same number is a DOM KPI. Data layer:
zod-validated adapter (`src/lib/api.ts`), `NEXT_PUBLIC_API_BASE` to repoint,
`NEXT_PUBLIC_USE_MOCK=1` for labelled demo data.

```bash
cd frontend && npm install
npm run dev            # http://localhost:3000
npm run typecheck && npm run build && npm run check:shaders   # all clean
```

## Configuration

- **Tenants & API keys:** `app/policy/tenants.yaml`
- **Policies:** `app/policy/policies/default.yaml` (+ per-tenant overrides) — thresholds,
  actions, allow/deny lists; editable live from the dashboard or `PUT /api/policies/{tenant}`
- **LLM tiers:** `.env` — `OLLAMA_BASE_URL`, `LOCAL_MODEL`, `OPENAI_API_KEY`,
  `OPENAI_BASE_URL`, `BIG_MODEL`
- **Cost model:** `COST_BIG_PER_1K`, `COST_LOCAL_PER_1K`, `AVG_RESPONSE_TOKENS`
- **Router tuning:** `BANDIT_ALPHA`, `BANDIT_COST_WEIGHT`, `BANDIT_LATENCY_WEIGHT`
- **Runtime state:** `data/` (audit.db, bandit_state.npz, learned_patterns.json,
  hard_examples.jsonl, redteam_history.jsonl) and `models/`

## Tests

```bash
pytest tests/ -v        # 41 passed
```

Covers: PII spans + Luhn, injection heuristics (base64, Kannada attack vs Kannada
benign, short greetings), phishing features + no-URL guard, policy precedence +
tenant fallback, LinUCB learning + persistence, audit hash-chain tamper detection,
end-to-end API (block/redact/allow, feedback, dashboard, health).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Chat says `Ollama not usable … 404` | Wrong port or a non-Ollama service on `OLLAMA_BASE_URL`; check `curl http://127.0.0.1:11434/api/tags` |
| First chat is slow (~13s) | One-time model load into VRAM; later calls are fast. Warm up with any first prompt |
| `401 Missing/Unknown API key` | Use a key from `app/policy/tenants.yaml` (`dev-default-key`) |
| Frontend shows "gateway offline" | Start the backend: `python run.py` in the project root |
| Cost saved stays $0.00 | You haven't used the Chat panel — only `/v1/chat` moves LLM metrics; scanning never calls an LLM |
| Big tier says "unconfigured" | Set `OPENAI_API_KEY` in `.env` — intentional honesty, no silent fallback |

## Honest limitations

- **Injection data caveat:** the four HF injection datasets share some origins; dedupe
  is exact-text only, so held-out metrics are mildly optimistic. The red-team ASR on
  held-out mutations (6.9%) is the more honest number.
- **Cost saved is an estimate** from configurable constants, not measured billing; the
  label says "est". Response tokens are assumed at `AVG_RESPONSE_TOKENS`.
- **Phishing ceiling:** F1 0.772 on real URLs with lexical features; benign
  top-domain homepages are "easy negatives". Upgrade path: char-CNN/transformer.
- **Bandit cold start:** rewards come from explicit feedback + red-team labels; the
  `rules` and `all` strategies stay selectable as honest baselines.
- **Rate limiter:** in-process token bucket; swap for Redis for multi-worker deploys.
- **Malware detector:** static features only — never executes samples.
- **PII regex coverage:** strong on cards/keys/government IDs/contacts; not a full NER.
  The spaCy/BERT-NER upgrade from the summary is the next step.

## Docker

```bash
cp .env.example .env
docker compose up --build     # gateway on :8000 (frontend runs separately: npm run build && npm start)
```
