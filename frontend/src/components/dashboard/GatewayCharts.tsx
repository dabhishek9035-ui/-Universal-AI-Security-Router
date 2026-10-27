'use client';
import { useQuery } from '@tanstack/react-query';
import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { gateway } from '@/lib/api';
import { useApiKey } from './useApiKey';

const DETECTOR_COLORS = ['#5de1ee', '#6cffc4', '#7ff3ff', '#b794ff', '#ffc27a'];

export default function GatewayCharts() {
  const [apiKey] = useApiKey();
  const { data } = useQuery({
    queryKey: ['metrics', apiKey],
    queryFn: () => gateway.metrics(apiKey),
    refetchInterval: 5_000,
  });

  const detectorData = Object.entries(data?.detector_runs ?? {}).map(([name, runs]) => ({
    name: name.replace('prompt_injection', 'injection').replace('log_anomaly', 'anomaly'),
    runs,
  }));
  const decisionData = Object.entries(data?.decisions ?? {})
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));
  const DECISION_COLORS: Record<string, string> = {
    allow: '#2f8f6b', block: '#c2506a', redact: '#c2903b', flag: '#8f6bd1', escalate: '#c25a50',
  };

  return (
    <div className="charts-grid">
      <div className="glass chart-card">
        <span className="data-label">Detector invocations</span>
        {detectorData.length === 0 ? (
          <ChartEmpty />
        ) : (
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={detectorData} margin={{ top: 12, right: 8, left: -18, bottom: 0 }}>
              <CartesianGrid stroke="rgba(166,217,228,.08)" vertical={false} />
              <XAxis dataKey="name" tick={{ fill: 'var(--muted)', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--muted)', fontSize: 10 }} axisLine={false} tickLine={false} allowDecimals={false} />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(166,217,228,.06)' }} />
              <Bar dataKey="runs" radius={[4, 4, 0, 0]}>
                {detectorData.map((_, i) => (
                  <Cell key={i} fill={DETECTOR_COLORS[i % DETECTOR_COLORS.length]} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
      <div className="glass chart-card">
        <span className="data-label">Policy decisions</span>
        {decisionData.length === 0 ? (
          <ChartEmpty />
        ) : (
          <ResponsiveContainer width="100%" height={230}>
            <PieChart>
              <Pie data={decisionData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={86} paddingAngle={3} strokeWidth={0}>
                {decisionData.map((d) => (
                  <Cell key={d.name} fill={DECISION_COLORS[d.name] ?? '#5de1ee'} fillOpacity={0.9} />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        )}
        <div className="chart-legend">
          {decisionData.map((d) => (
            <span key={d.name} className="legend-item">
              <i style={{ background: DECISION_COLORS[d.name] ?? '#5de1ee' }} /> {d.name} · {d.value}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

function ChartEmpty() {
  return <p className="muted-paragraph chart-empty">No traffic yet — scan something above.</p>;
}

function ChartTooltip({ active, payload, label }: {
  active?: boolean; payload?: Array<{ name?: string; value?: number | string }>; label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      {payload.map((p, i) => (
        <div key={i}>
          {label ?? p.name}: <b>{typeof p.value === 'number' ? p.value.toLocaleString('en-US') : p.value}</b>
        </div>
      ))}
    </div>
  );
}
