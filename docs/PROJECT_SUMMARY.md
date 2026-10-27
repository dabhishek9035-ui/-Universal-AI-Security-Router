# Universal AI Security Router: Project Summary

## 1. The Idea

A security gateway that sits in front of any application or LLM. Any input goes in (prompt, email, URL, log, file, network traffic). A learned router decides which specialist model(s) should inspect it, a policy engine decides what to do (allow, block, redact, flag, escalate), and clean LLM requests are routed to the cheapest capable model. A red-team module continuously attacks the system and retrains it.

**Problem it solves:** every app adding an LLM or handling user data faces prompt injection, data leaks, phishing, and anomalies, and today each needs a separate tool. This gives one plug-and-play layer for all of them, while cutting compute and API cost via routing.

**Use cases:** company chatbots, college/hospital PII protection, email and SOC triage, developer API gateway for LLM apps, IoT/network monitoring.

**Novelty / research angle:**
1. Learned (bandit/RL) routing across heterogeneous security models, optimizing accuracy vs. cost vs. latency
2. Closed-loop adversarial retraining (attack generator -> hard examples -> retrain)
3. One unified, explainable, multi-tenant system instead of isolated tools

---

## 2. Architecture

```
Client / App
    |
    v
[API Gateway: FastAPI, auth, rate limit]
    |
    v
[Input Type Detector]  -> prompt / email / URL / log / file / traffic
    |
    v
[Learned Router]  -> picks detector(s) by expected accuracy, cost, latency
    |
    v
[Specialist Detectors]  (run in parallel when ambiguous)
  - Prompt injection / jailbreak
  - PII / secret leak (DLP)
  - Phishing / malicious URL
  - Log / network anomaly
  - Malware / file
    |
    v
[Policy Engine]  per-tenant rules -> allow / block / redact / flag / escalate
    |
    +--> [Audit Log + Explainability]
    |
    v  (if allowed)
[LLM Router]  easy -> local quantized model, hard -> big API model
    |
    v
[Output Guard]  re-scan response for leaks / unsafe content
    |
    v
Response to client

Side loops:
[Red-Team Module] -> attacks -> failures -> hard-example buffer -> retrain detectors
[Dashboard] <- reads audit log, metrics, routing stats, cost savings
```

---

## 3. Components in Detail

### 3.1 Input Type Detector
- Stage 1: rules (file extension, MIME, regex for URL/email headers/log formats)
- Stage 2: small classifier (TF-IDF + LR or tiny transformer) for ambiguous inputs
- Output: type + confidence

### 3.2 Specialist Detectors

| Detector | Model approach | Output |
|---|---|---|
| Prompt injection / jailbreak | Fine-tuned DeBERTa-v3-small / DistilBERT, plus heuristic features (override phrases, role-switch, encoding tricks) | score + attack category |
| PII / secrets (DLP) | Regex + detect-secrets patterns + NER (spaCy / BERT-NER) | entities + spans for redaction |
| Phishing / malicious URL | URL: char-level CNN/transformer + lexical features (length, entropy, TLD, IP host). Email: text classifier + header features | score + reasons |
| Log / network anomaly | Autoencoder, Isolation Forest, optional small transformer on log sequences; flow features for traffic | anomaly score + offending features |
| Malware / file | Gradient boosting on static features (EMBER-style: byte histograms, imports, entropy) | score + family guess |

All detectors share one interface: `predict(input) -> {label, score, explanation}`.

### 3.3 Learned Router
- **Formulation:** contextual bandit. Context = input features (type, length, source, entropy, tenant). Arms = detector subsets. Reward = correctness - lambda1*cost - lambda2*latency.
- **Algorithms:** LinUCB or Thompson sampling. Compare against: rule-based, run-everything, random.
- **Cold start:** begin with rules, let the bandit explore with low probability, learn online from labeled feedback / red-team ground truth.

### 3.4 LLM Router
- Difficulty classifier over the prompt (length, task type, reasoning cues, embedding-based) decides: local quantized model (Ollama/llama.cpp, 3B-8B 4-bit) vs. large API model.
- Trained on pairs: (prompt, did the small model answer well?) with an LLM-as-judge for labels.
- Fallback: if small model confidence is low, escalate.

### 3.5 Policy Engine
- Per-tenant config (YAML/JSON): thresholds per detector, action per category, redaction rules, allow/deny lists.
- Example: `pii.score > 0.8 -> redact`, `injection.score > 0.9 -> block`, `anomaly.score > 0.7 -> flag + alert`.
- Hot-reloadable, versioned.

### 3.6 Audit + Explainability
- Hash-chained audit rows (request ID, input hash, router decision, detector outputs, action, timestamp).
- Explanations: SHAP / attention highlights for text, feature importance for URL/logs/files, human-readable "blocked because..." reasons.

### 3.7 Red-Team Module (Adversarial Layer)
- **Attack generation:** LLM-based mutation (paraphrase, obfuscation, base64/leetspeak, multilingual including Kannada, indirect injection via documents), templates from Garak / HackAPrompt.
- **Loop:** generate attacks -> run through system -> record misses -> add to hard-example buffer -> retrain -> re-measure.
- **Metric:** attack success rate (ASR) per detector per round.

### 3.8 Dashboard
- Live request feed, threats by type, routing decisions, cost saved, latency, per-tenant policy editor, audit viewer, explanation view.

---

## 4. Data Required

| Area | Datasets |
|---|---|
| Prompt injection / jailbreak | deepset/prompt-injections, HackAPrompt, JailbreakBench, Garak probes, self-generated variants |
| PII / secrets | ai4privacy PII dataset, synthetic via Faker (names, Aadhaar-like, phone, email, cards), leaked-key patterns from detect-secrets |
| Phishing / URL | PhishTank, OpenPhish, UCI phishing, Mendeley URL datasets, Tranco (benign domains) |
| Email | Enron (benign), SpamAssassin, Nazario phishing corpus |
| Network anomaly | CIC-IDS2017/2018, UNSW-NB15, NSL-KDD |
| Log anomaly | LogHub (HDFS, BGL, Thunderbird) |
| Malware | EMBER (feature vectors, no live malware needed) |
| LLM routing | LMSYS / Chatbot Arena data, RouteLLM datasets, your own prompts labeled by judge model |
| Benchmark | Your own held-out set + red-team generated set |

**Data handling rules:**
- Strict train/val/test split, no leakage (dedupe near-duplicates, split by source/time where possible)
- Class imbalance: weighted loss, focal loss, or resampling (security data is heavily imbalanced)
- Synthetic data: always spot-check a sample manually
- Never use live malware; stick to feature-level datasets

---

## 5. Methodology

1. **Baseline first:** classic ML (TF-IDF + LR/XGBoost) for every detector to set a floor.
2. **Upgrade:** fine-tune small transformers / train autoencoders. Compare against baseline.
3. **Calibration:** temperature scaling so scores mean something; thresholds chosen on validation set per policy (precision-first vs. recall-first).
4. **Router training:** offline replay on logged data, then online bandit updates.
5. **Robustness:** red-team loop, adversarial training with hard examples.
6. **Explainability:** SHAP/attention for each detector, checked for sanity.
7. **Ablations:** router on/off, red-team on/off, ensemble vs. single detector, local-only vs. hybrid LLM routing.

---

## 6. Pipelines

**Training pipeline (per detector):**
raw data -> clean/dedupe -> split -> feature extraction/tokenization -> train -> calibrate -> evaluate -> log to MLflow -> export (ONNX / quantized) -> register model version.

**Inference pipeline (per request):**
auth -> type detect -> route -> detectors (parallel) -> aggregate scores -> policy decision -> redact/block/pass -> LLM route -> output guard -> audit log -> response.

**Red-team / retraining pipeline:**
attack generator -> run against live pipeline in sandbox -> collect misses -> label/verify -> hard-example buffer -> periodic retrain -> evaluate on fixed benchmark + new attacks -> promote if better.

**Monitoring pipeline:**
metrics (latency, throughput, detection rates, drift) -> dashboard -> alerts when score distributions shift (data drift) or ASR rises.

---

## 7. Tech Stack

| Layer | Tools |
|---|---|
| ML | PyTorch, HuggingFace Transformers, scikit-learn, XGBoost, SHAP |
| Router | LinUCB / Thompson sampling (custom or `mabwiser`) |
| Local LLM | Ollama / llama.cpp, 3B-8B 4-bit (fits RTX 4050 6GB) |
| Backend | FastAPI (async), Redis, PostgreSQL |
| Frontend | Next.js, Tailwind, Recharts |
| MLOps | MLflow / W&B, Docker, GitHub Actions |
| Red-team | Garak, custom LLM-based attack generator |
| Serving | ONNX Runtime / quantization for CPU-friendly small models |

---

## 8. Evaluation

| What | Metric |
|---|---|
| Each detector | Precision, recall, F1, AUC-ROC/PR, confusion matrix |
| Router | Routing accuracy, % compute saved vs. run-everything, regret vs. oracle |
| LLM router | Cost saved vs. always-big-model at equal answer quality (judge-scored) |
| System | p50/p95 latency, throughput (req/s), overhead vs. no-gateway |
| Robustness | ASR before vs. after red-team retraining |
| Explainability | Human review of explanation quality on a sample |

**Baselines to beat:** no-router (run everything), rule-based routing, single general-purpose LLM-as-guard.

---

## 9. Optional Scale-Ups (pick one)

- Federated learning across tenants (Flower): improve detectors without sharing raw data
- Model-poisoning defense: detect tampered training updates/data
- Policy auto-patch agent: LLM agent proposes policy changes from observed attacks, human approves

---

## 10. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| 6GB VRAM | Small models, 4-bit quantization, Colab/Kaggle for heavy training |
| Imbalanced / noisy data | Weighted loss, calibration, manual spot-checks |
| Router no better than rules | Report honestly; hybrid rules + bandit |
| Detector false positives hurt usability | Per-tenant thresholds, "flag" action instead of hard block |
| Gateway itself attacked | Test auth, input size limits, rate limiting, treat router inputs as untrusted |
| Scope creep | Core = injection + PII + phishing + anomaly + router + red-team. Malware and scale-ups are optional. |

---

## 11. Minimum Viable Version

Prompt-injection + PII + phishing detectors, rule/bandit router, policy engine, audit log, red-team loop, basic dashboard. Strong enough on its own as a final-year project.
