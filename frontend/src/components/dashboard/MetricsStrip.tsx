'use client';
import { useQuery } from '@tanstack/react-query';
import { useEffect } from 'react';
import { gateway } from '@/lib/api';
import { useStore } from '@/state/store';
import { useApiKey } from './useApiKey';

const DECISION_LABELS: Record<string, string> = {
  allow: 'Allowed',
  block: 'Blocked',
  redact: 'Redacted',
  flag: 'Flagged',
  escalate: 'Escalated',
};

export default function MetricsStrip() {
  const [apiKey] = useApiKey();
  const setThreatLevel = useStore((s) => s.setThreatLevel);
  const { data, isError } = useQuery({
    queryKey: ['metrics', apiKey],
    queryFn: () => gateway.metrics(apiKey),
    refetchInterval: 5_000,
  });

  const blocked = data?.decisions.block ?? 0;
  const total = data?.requests_total ?? 0;
  const blockedPct = total > 0 ? blocked / total : 0;

  useEffect(() => {
    // the orb eases toward this; the DOM shows the same number below
    setThreatLevel(Math.min(0.985, Math.max(0.015, blockedPct)));
  }, [blockedPct, setThreatLevel]);

  const llmLocal = data?.llm_tier_calls?.local ?? 0;
  const llmBig = data?.llm_tier_calls?.big ?? 0;

  const cards = [
    { label: 'Requests', value: fmt(data?.requests_total), hint: 'scanned by the gateway' },
    { label: 'Blocked', value: fmt(blocked), hint: pct(total, blocked), accent: true },
    { label: 'Redacted', value: fmt(data?.decisions.redact), hint: 'PII masked' },
    { label: 'p95 latency', value: data ? `${data.latency_ms.p95.toFixed(1)}ms` : '—', hint: `p50 ${data ? data.latency_ms.p50.toFixed(1) : '—'}ms` },
    { label: 'Cost saved', value: data ? `$${data.cost.usd_saved.toFixed(4)}` : '—', hint: `${data ? data.cost.est_savings_pct.toFixed(0) : 0}% vs always-big · ${llmLocal} local / ${llmBig} big calls` },
  ];

  if (isError) {
    return (
      <div className="metrics-strip glass" role="status">
        <span className="mono-muted">gateway unreachable — start it with <code>python run.py</code></span>
      </div>
    );
  }

  return (
    <div className="metrics-strip" aria-label="Live gateway metrics">
      {cards.map((c) => (
        <div key={c.label} className={`glass metric-card${c.accent ? ' metric-accent' : ''}`}>
          <span className="data-label">{c.label}</span>
          <span className={`metric-value${c.value === undefined ? ' skeleton' : ''}`}>
            {c.value ?? '0000'}
          </span>
          <span className="metric-hint">{c.hint}</span>
        </div>
      ))}
      <div className="glass metric-card threat-card">
        <span className="data-label">Threat pressure</span>
        <span className="metric-value">{(blockedPct * 100).toFixed(1)}%</span>
        <div className="threat-bar" aria-hidden>
          <i style={{ width: `${Math.max(3, blockedPct * 100)}%` }} />
        </div>
        <span className="metric-hint">{DECISION_LABELS.block} share — drives the orb</span>
      </div>
    </div>
  );
}

function fmt(v: number | undefined): string {
  return v === undefined ? '—' : v.toLocaleString('en-US');
}
function pct(total: number, part: number): string {
  return total > 0 ? `${((part / total) * 100).toFixed(1)}% of traffic` : 'of traffic';
}
