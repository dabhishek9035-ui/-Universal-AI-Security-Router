'use client';
import { useMutation, useQuery } from '@tanstack/react-query';
import { gateway } from '@/lib/api';
import { useApiKey } from './useApiKey';

export default function RedTeamPanel() {
  const [apiKey] = useApiKey();
  const run = useMutation({ mutationFn: (n: number) => gateway.runRedTeam(apiKey, n) });
  const history = useQuery({
    queryKey: ['redteam-history', apiKey],
    queryFn: () => gateway.redTeamHistory(apiKey),
    enabled: run.isSuccess || run.isIdle,
  });

  const asrRows = Object.entries(run.data?.asr_by_category ?? {})
    .filter(([cat]) => cat !== 'benign')
    .sort((a, b) => b[1] - a[1]);
  const rounds = history.data?.rounds.slice(-10).reverse() ?? [];

  return (
    <div className="redteam-grid">
      <div className="glass redteam-card">
        <span className="data-label">Adversarial round</span>
        <p className="muted-paragraph">
          Generates mutated attacks (base64, leetspeak, document-wrapping, Kannada), scans
          them through the live pipeline, records every miss into the hard-example buffer
          and learns patterns from it.
        </p>
        <div className="console-actions">
          <button className="btn btn-primary" onClick={() => run.mutate(40)} disabled={run.isPending}>
            {run.isPending ? 'Attacking…' : 'Run a round'}
          </button>
          {run.data && (
            <span className="mono-muted">
              {run.data.n_attacks} attacks · {run.data.misses} missed · {run.data.false_positives_on_benign} FPs
            </span>
          )}
        </div>
        {run.data && (
          <>
            <div className="asr-headline">
              <span>Attack success rate</span>
              <b className={run.data.asr_overall > 0.2 ? 'asr-bad' : 'asr-ok'}>
                {(run.data.asr_overall * 100).toFixed(1)}%
              </b>
            </div>
            <div className="asr-rows">
              {asrRows.map(([cat, asr]) => (
                <div key={cat} className="asr-row">
                  <span className="mono-muted">{cat}</span>
                  <div className="threat-bar"><i style={{ width: `${Math.max(2, asr * 100)}%` }} /></div>
                  <span className="mono-muted">{(asr * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
      <div className="glass redteam-card">
        <span className="data-label">ASR history (lower is better)</span>
        {rounds.length === 0 ? (
          <p className="muted-paragraph">No rounds recorded yet — run one.</p>
        ) : (
          <table className="audit-table">
            <thead><tr><th>round</th><th>attacks</th><th>ASR</th></tr></thead>
            <tbody>
              {rounds.map((r) => (
                <tr key={r.round_id}>
                  <td className="mono-muted">{r.round_id.slice(0, 28)}</td>
                  <td>{r.n_attacks}</td>
                  <td className={r.asr_overall > 0.2 ? 'asr-bad' : 'asr-ok'}>
                    {(r.asr_overall * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
