import { z } from 'zod';

const DetectionOut = z.object({
  detector: z.string(),
  label: z.string(),
  score: z.number(),
  category: z.string().nullable(),
  explanation: z.string(),
});

const RouterDecision = z.object({
  strategy: z.string(),
  detectors_run: z.array(z.string()).default([]),
});

export const ChatResponse = z.object({
  request_id: z.string(),
  tenant: z.string(),
  input_type: z.string(),
  decision: z.string(),
  reasons: z.array(z.string()).default([]),
  detections: z.array(DetectionOut).default([]),
  redacted_text: z.string().nullable(),
  router: RouterDecision,
  latency_ms: z.number(),
  answer: z.string().nullable(),
  llm: z.record(z.string(), z.unknown()),
  output_guard: z.array(DetectionOut).default([]),
});

export type ChatResponseT = z.infer<typeof ChatResponse>;
