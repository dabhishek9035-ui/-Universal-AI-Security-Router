# Architecture — Implementation Map

This maps the design in [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) to the actual code.

```
Client / App
    |
    v
[API Gateway]                app/main.py, app/gateway/{auth,ratelimit}.py
    |                        - X-API-Key -> tenant (tenants.yaml), token-bucket 429s
    v
[Input Type Detector]        app/detection/type_detector.py
    |                        - Stage 1 rules: URL/email-header/log-format/file/flow
    |                        - Stage 2 optional TF-IDF classifier (models/input_type.joblib)
    v                        returns (type, confidence)
[Learned Router]             app/router/security_router.py, app/router/bandit.py
    |                        - LinUCB disjoint model per arm
    |                        - context: [bias, log_len, entropy, tenant_risk, type one-hot]
    |                        - arms: mandatory base + optional detector subsets per type
    |                        - strategies: bandit | rules | all (baselines kept)
    v
[Specialist Detectors]       app/detection/*.py  (parallel via ThreadPoolExecutor)
  - prompt_injection         weighted pattern families + b64/homoglyph + optional LR blend
  - pii (DLP)                regex + Luhn -> exact spans
  - phishing                 URL lexical/host features + email header mismatch
  - log_anomaly              template-mining z-scores / flow z-scores / optional iForest
  - malware                  static features only (entropy, ext risk, imports, packers)
    |                        shared interface: predict(payload, type) -> Detection
    v
[Policy Engine]              app/policy/engine.py, app/policy/policies/{tenant}.yaml
    |                        - hot-reload on mtime, per-tenant fallback to default
    |                        - precedence: block > escalate > redact > flag > allow
    |                        - reasons list = human-readable "blocked because..."
    +--> [Audit Log]         app/audit/audit_log.py
    |                        - SQLite, SHA-256 hash chain, verify() walks + detects tamper
    v  (if allowed)
[LLM Router]                 app/router/llm_router.py
    |                        - difficulty features -> local 4-bit vs big API
    |                        - escalation: local failure/timeout -> big model
    v
[LLM Providers]              app/llm/providers.py  (Ollama + OpenAI-compatible via httpx)
    |
    v
[Output Guard]               app/detection/output_guard.py
                             - re-scan response: PII spans redacted, echoed injections flagged

Side loops:
[Red-Team Module]            app/redteam/attacks.py, app/redteam/loop.py
    attacks (7 mutation families: plain, paraphrase, leetspeak, base64,
    indirect-document, fake-delimiter, upper; + Kannada injections)
    -> scan() in-process -> misses -> data/hard_examples.jsonl
    -> learned patterns (data/learned_patterns.json, hot-loaded by detector)
    -> bandit rewards -> ASR per category -> data/redteam_history.jsonl
[Dashboard]                  app/dashboard/api.py + templates/index.html
    reads /api/metrics, /api/audit, chain verify; triggers red-team rounds;
    edits policies (writes tenant yaml, hot-reloaded)
```

## Key invariants

1. **Every detector implements the same interface** (`app/detection/base.py`):
   `predict(payload, input_type) -> Detection{label, score, category, explanation, spans}`.
   Adding a detector = one class + registry entry + (optionally) router mandatory set.
2. **Scores are comparable across detectors** (0..1); thresholds live in policy YAML,
   not in code — calibration changes are a config edit.
3. **The audit log is tamper-evident**: each row hashes the previous row's hash over a
   canonical JSON body; `/api/audit/verify` and `AuditLog.verify()` detect any
   mutation or deletion.
4. **Graceful degradation**: trained models are optional blends; Ollama down =>
   escalate to big API; big API unconfigured => honest 503-style response, never a
   silently unguarded completion (input scan still ran, output guard still runs).
5. **Router honesty**: `rules` and `all` strategies remain selectable so the bandit
   can always be measured against baselines (evaluation §8 of the summary).

## Reward design (security router)

`reward = correctness − λ₁·Σ(cost) − λ₂·latency` (λ from env, defaults 0.1 / 0.05).
Correctness sources: `/v1/feedback` labels and red-team ground truth. Pseudo-labeling
from ensemble consensus is deliberately *not* used for updates to avoid self-confirming
routing.

## What to upgrade next (in order of value)

1. Replace synthetic training data with the real datasets (summary §4) + strict
   train/val/test splits.
2. Fine-tune DeBERTa-v3-small for injection (6GB VRAM OK with 4-bit/LoRA), blend with
   the heuristic score.
3. LLM-as-judge labeling for real LLM-router training pairs (summary §3.4).
4. Redis-backed rate limiting + multi-worker uvicorn.
5. Next.js/Tailwind/Recharts dashboard on the existing `/api/*` contract.
6. MLflow tracking in the train scripts' `print` points.
