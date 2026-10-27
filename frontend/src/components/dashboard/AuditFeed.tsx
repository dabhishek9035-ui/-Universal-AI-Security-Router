'use client';
import { useQuery } from '@tanstack/react-query';
import { gateway } from '@/lib/api';
import { useApiKey } from './useApiKey';

export default function AuditFeed() {
  const [apiKey] = useApiKey();
  const { data, isError } = useQuery({
    queryKey: ['audit', apiKey],
    queryFn: () => gateway.audit(apiKey, 14),
    refetchInterval: 5_000,
  });
  const chain = useQuery({
    queryKey: ['chain', apiKey],
    queryFn: () => gateway.verifyChain(apiKey),
    refetchInterval: 30_000,
  });

  return (
    <div className="glass audit-card">
      <div className="audit-head">
        <span className="data-label">Audit log — hash-chained, tamper-evident</span>
        <span className={`pill ${chain.data?.ok ? 'pill-allow' : 'pill-block'}`}>
          {chain.isError
            ? 'gateway offline'
            : chain.data?.ok
              ? `chain verified · ${chain.data.checked} rows`
              : `TAMPERED at row ${chain.data?.first_bad_id}`}
        </span>
      </div>
      {isError ? (
        <p className="muted-paragraph">Audit feed needs a reachable gateway and a valid API key.</p>
      ) : (
        <div className="audit-scroll">
          <table className="audit-table">
            <thead>
              <tr>
                <th>time</th><th>type</th><th>decision</th><th>detectors</th><th>why</th><th>ms</th>
              </tr>
            </thead>
            <tbody>
              {(data?.rows ?? []).map((r) => (
                <tr key={r.id}>
                  <td className="mono-muted">{new Date(r.ts * 1000).toLocaleTimeString()}</td>
                  <td>{r.input_type}</td>
                  <td><span className={`pill pill-${r.decision}`}>{r.decision}</span></td>
                  <td className="mono-muted">{r.detections.map((d) => d.detector.replace('prompt_injection', 'injection')).join(', ') || '—'}</td>
                  <td className="why-cell mono-muted">{r.reasons.join('; ').slice(0, 120) || '—'}</td>
                  <td className="mono-muted">{r.latency_ms.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {(data?.rows.length ?? 0) === 0 && <p className="muted-paragraph">No requests yet.</p>}
        </div>
      )}
    </div>
  );
}
