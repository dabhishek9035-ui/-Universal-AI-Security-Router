'use client';
import MetricsStrip from '@/components/dashboard/MetricsStrip';
import ScanConsole from '@/components/dashboard/ScanConsole';
import ChatPanel from '@/components/dashboard/ChatPanel';
import GatewayCharts from '@/components/dashboard/GatewayCharts';
import AuditFeed from '@/components/dashboard/AuditFeed';
import RedTeamPanel from '@/components/dashboard/RedTeamPanel';
import { useApiKey } from '@/components/dashboard/useApiKey';
import Reveal from '@/components/Reveal';

export default function Home() {
  const [apiKey, setApiKey] = useApiKey();

  return (
    <>
      <section className="hero">
        <div className="eyebrow"><i /> UNIVERSAL AI SECURITY GATEWAY</div>
        <h1>Every request inspected.<br /><span>Every token routed.</span></h1>
        <p className="lead">
          One plug-and-play layer in front of any app or LLM: a learned router picks the
          specialist detectors, a policy engine allows, blocks, redacts or escalates, and a
          red-team loop keeps retraining the whole thing.
        </p>
        <div className="actions">
          <a className="btn btn-primary" href="#console">Run a scan</a>
          <a className="btn btn-ghost" href="#redteam">Attack the gateway ↗</a>
        </div>
        <p className="hero-foot mono-muted">Local demo · FastAPI on :8000 · dev key from app/policy/tenants.yaml</p>
      </section>

      <section id="live" className="section" aria-label="Live metrics">
        <MetricsStrip />
      </section>

      <section id="console" className="section">
        <div className="section-head">
          <span className="eyebrow"><i /> LIVE SCAN CONSOLE</span>
          <label className="apikey-field">
            <span className="data-label">API key</span>
            <input
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value.trim())}
              spellCheck={false}
              aria-label="Tenant API key"
              size={16}
            />
          </label>
        </div>
        <Reveal><ScanConsole /></Reveal>
      </section>

      <section id="chat" className="section">
        <div className="section-head"><span className="eyebrow"><i /> GUARDED LLM CHAT — LOCAL VS BIG ROUTING</span></div>
        <Reveal><ChatPanel /></Reveal>
      </section>

      <section id="detections" className="section">
        <div className="section-head"><span className="eyebrow"><i /> WHAT THE ROUTER DID</span></div>
        <Reveal><GatewayCharts /></Reveal>
      </section>

      <section id="audit" className="section">
        <div className="section-head"><span className="eyebrow"><i /> EVERY DECISION, ON THE RECORD</span></div>
        <Reveal><AuditFeed /></Reveal>
      </section>

      <section id="redteam" className="section">
        <div className="section-head"><span className="eyebrow"><i /> CLOSED-LOOP ADVERSARIAL RETRAINING</span></div>
        <Reveal><RedTeamPanel /></Reveal>
      </section>

      <section className="section last">
        <Reveal>
          <div className="glass panel cta">
            <h2>The loop never stops.</h2>
            <p className="muted-paragraph">
              Missed attacks land in a hard-example buffer, become learned patterns on the next
              round, and the bandit keeps re-balancing detector cost against accuracy. Retrain on
              real datasets any time with the scripts in <code>/scripts</code>.
            </p>
            <a className="btn btn-primary" href="#console">Scan something</a>
          </div>
        </Reveal>
      </section>
    </>
  );
}
