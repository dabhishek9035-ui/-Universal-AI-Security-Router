import { z } from 'zod';

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://127.0.0.1:8000';
export const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === '1';

// ---------- schemas (mirror the FastAPI responses) ----------

const DetectionOut = z.object({
  detector: z.string(),
  label: z.string(),
  score: z.number(),
  category: z.string().nullable(),
  explanation: z.string(),
  spans: z.array(z.unknown()).default([]),
});

const RouterDecision = z.object({
  strategy: z.string(),
  detectors_run: z.array(z.string()).default([]),
  skipped: z.array(z.string()).default([]),
  context: z.record(z.string(), z.unknown()).default({}),
});

export const ScanResponse = z.object({
  request_id: z.string(),
  tenant: z.string(),
  input_type: z.string(),
  decision: z.string(),
  reasons: z.array(z.string()).default([]),
  detections: z.array(DetectionOut).default([]),
  redacted_text: z.string().nullable(),
  router: RouterDecision,
  latency_ms: z.number(),
});
export type ScanResponseT = z.infer<typeof ScanResponse>;

export const Metrics = z.object({
  requests_total: z.number(),
  decisions: z.record(z.string(), z.number()),
  by_input_type: z.record(z.string(), z.number()),
  detector_runs: z.record(z.string(), z.number()),
  llm_tier_calls: z.record(z.string(), z.number()).optional(),
  router_strategy_counts: z.record(z.string(), z.number()).optional(),
  latency_ms: z.object({ p50: z.number(), p95: z.number() }),
  detector_latency_p95_ms: z.record(z.string(), z.number()).optional(),
  cost: z.object({
    usd_actual: z.number(),
    usd_if_always_big: z.number(),
    usd_saved: z.number(),
    est_savings_pct: z.number(),
  }),
  audit_total: z.number().optional(),
});
export type MetricsT = z.infer<typeof Metrics>;

const AuditRow = z.object({
  id: z.number(),
  ts: z.number(),
  request_id: z.string(),
  tenant: z.string(),
  input_type: z.string(),
  decision: z.string(),
  reasons: z.array(z.string()).default([]),
  detections: z.array(DetectionOut).default([]),
  latency_ms: z.number(),
});
export const AuditRows = z.object({ rows: z.array(AuditRow) });
export type AuditRowT = z.infer<typeof AuditRow>;

export const ChainVerify = z.object({
  ok: z.boolean(),
  checked: z.number(),
  first_bad_id: z.number().nullable(),
});
export type ChainVerifyT = z.infer<typeof ChainVerify>;

export const RedTeamSummary = z.object({
  round_id: z.string(),
  n_attacks: z.number(),
  misses: z.number(),
  asr_overall: z.number(),
  asr_by_category: z.record(z.string(), z.number()),
  false_positives_on_benign: z.number(),
});
export type RedTeamSummaryT = z.infer<typeof RedTeamSummary>;

export const RedTeamHistory = z.object({
  rounds: z.array(
    z.object({
      round_id: z.string(),
      asr_overall: z.number(),
      n_attacks: z.number(),
      ts: z.number(),
    }),
  ),
});

// ---------- adapter ----------

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, apiKey: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
      ...(init?.headers ?? {}),
    },
  });
  if (!resp.ok) {
    let detail = `${resp.status}`;
    try {
      const body = (await resp.json()) as { detail?: unknown };
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
    } catch { /* keep status code */ }
    throw new ApiError(detail, resp.status);
  }
  return (await resp.json()) as T;
}

function parsed<T>(schema: z.ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value);
  if (!result.success) throw new ApiError('Unexpected response shape from gateway', 0);
  return result.data;
}

export const api = {
  health: async () => {
    const raw = await fetch(`${API_BASE}/healthz`).then((r) => r.json());
    return raw as { status: string; audit_chain: boolean };
  },

  chat: (apiKey: string, text: string) =>
    request<unknown>('/v1/chat', apiKey, {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),

  scan: (apiKey: string, text: string, declaredType: string) =>
    request<unknown>('/v1/scan', apiKey, {
      method: 'POST',
      body: JSON.stringify({ text, declared_type: declaredType }),
    }).then((v) => parsed(ScanResponse, v)),

  metrics: (apiKey: string) =>
    request<unknown>('/api/metrics', apiKey).then((v) => parsed(Metrics, v)),

  audit: (apiKey: string, limit = 14) =>
    request<unknown>(`/api/audit?limit=${limit}`, apiKey).then((v) => parsed(AuditRows, v)),

  verifyChain: (apiKey: string) =>
    request<unknown>('/api/audit/verify', apiKey).then((v) => parsed(ChainVerify, v)),

  runRedTeam: (apiKey: string, nAttacks = 40) =>
    request<unknown>(`/api/redteam/run?n_attacks=${nAttacks}`, apiKey, { method: 'POST' }).then(
      (v) => parsed(RedTeamSummary, v),
    ),

  redTeamHistory: (apiKey: string) =>
    request<unknown>('/api/redteam/history?limit=20', apiKey).then((v) => parsed(RedTeamHistory, v)),
};

// ---------- labelled mock (NEXT_PUBLIC_USE_MOCK=1) ----------

const mockMetrics: MetricsT = {
  requests_total: 128,
  decisions: { allow: 74, block: 31, redact: 17, flag: 6, escalate: 0 },
  by_input_type: { prompt: 90, url: 22, email: 10, log: 6 },
  detector_runs: { prompt_injection: 96, pii: 96, phishing: 34, log_anomaly: 6, malware: 0 },
  latency_ms: { p50: 6.2, p95: 12.4 },
  cost: { usd_actual: 0.004, usd_if_always_big: 0.081, usd_saved: 0.077, est_savings_pct: 95.1 },
  audit_total: 128,
};

const mockScan = (text: string): ScanResponseT => ({
  request_id: 'mock-0001',
  tenant: 'default',
  input_type: 'prompt',
  decision: 'redact',
  reasons: ['pii score 0.96 > 0.5 -> redact (category: credit_card)'],
  detections: [
    {
      detector: 'prompt_injection',
      label: 'benign',
      score: 0.12,
      category: null,
      explanation: '[model+heuristics] no injection patterns matched',
      spans: [],
    },
    {
      detector: 'pii',
      label: 'pii',
      score: 0.96,
      category: 'credit_card',
      explanation: 'found 2 item(s): credit_card, email',
      spans: [],
    },
  ],
  redacted_text: text.replace(/\d/g, '•'),
  router: { strategy: 'bandit', detectors_run: ['prompt_injection', 'pii'], skipped: [], context: {} },
  latency_ms: 6.4,
});

export const mockApi = {
  health: async () => ({ status: 'ok', audit_chain: true }),
  chat: async (): Promise<unknown> => ({}),
  scan: async (_key: string, text: string) => mockScan(text),
  metrics: async () => mockMetrics,
  audit: async () => ({ rows: [] as AuditRowT[] }),
  verifyChain: async () => ({ ok: true, checked: 0, first_bad_id: null }),
  runRedTeam: async () =>
    ({
      round_id: 'mock-round',
      n_attacks: 40,
      misses: 3,
      asr_overall: 0.075,
      asr_by_category: { injection: 0, phishing: 0.125, override: 0.1 },
      false_positives_on_benign: 0,
    }) satisfies RedTeamSummaryT,
  redTeamHistory: async () => ({ rounds: [] }),
};

export const gateway = USE_MOCK ? mockApi : api;
