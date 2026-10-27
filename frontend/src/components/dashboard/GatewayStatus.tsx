'use client';
import { useQuery } from '@tanstack/react-query';
import { gateway } from '@/lib/api';

/** Small header pill: gateway reachable + audit chain intact. */
export default function GatewayStatus() {
  const { data, isError } = useQuery({
    queryKey: ['health'],
    queryFn: () => gateway.health(),
    refetchInterval: 10_000,
  });
  if (isError) return <span className="status-pill status-off">gateway offline</span>;
  if (!data) return <span className="status-pill status-unknown">connecting…</span>;
  return (
    <span className={`status-pill ${data.audit_chain ? 'status-on' : 'status-warn'}`}>
      {data.status === 'ok' && data.audit_chain ? 'gateway online' : 'degraded'}
    </span>
  );
}
