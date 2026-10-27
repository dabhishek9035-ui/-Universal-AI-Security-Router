'use client';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { gateway } from '@/lib/api';
import { ChatResponse, type ChatResponseT } from '@/lib/chatSchema';
import { useApiKey } from './useApiKey';

const CHAT_EXAMPLES = [
  'In one sentence, what is a prompt injection attack?',
  'Summarize the TCP vs UDP difference in two lines.',
  'Prove that the halting problem is undecidable, step by step.',
];

export default function ChatPanel() {
  const [apiKey] = useApiKey();
  const [text, setText] = useState('In one sentence, what is a prompt injection attack?');
  const chat = useMutation({
    mutationFn: async () => ChatResponse.parse(await gateway.chat(apiKey, text)),
  });

  return (
    <div className="chat-grid">
      <div className="glass chat-input">
        <span className="data-label">Prompt — the gateway scans it, routes it, guards the answer</span>
        <textarea
          aria-label="Prompt for the guarded chat"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          spellCheck={false}
        />
        <div className="console-actions">
          <button
            className="btn btn-primary"
            onClick={() => chat.mutate()}
            disabled={chat.isPending || text.trim().length === 0}
          >
            {chat.isPending ? 'Routing…' : 'Send'}
          </button>
          {CHAT_EXAMPLES.map((ex) => (
            <button key={ex} className="btn btn-ghost btn-chip" onClick={() => setText(ex)}>
              {ex.length > 34 ? `${ex.slice(0, 34)}…` : ex}
            </button>
          ))}
        </div>
        <p className="mono-muted">
          Easy prompts go to the local 4-bit model (free) · hard ones would go to the big API
          model · the first call loads the model into VRAM and is slow once.
        </p>
      </div>
      <div className="glass chat-result">
        <span className="data-label">Routed response</span>
        {chat.isError ? (
          <p className="error-text" role="alert">{chat.error instanceof Error ? chat.error.message : 'request failed'}</p>
        ) : chat.data ? (
          <ChatResult data={chat.data} />
        ) : (
          <p className="muted-paragraph">Send a prompt to watch the LLM router pick a tier and the output guard scan the answer.</p>
        )}
      </div>
    </div>
  );
}

type LlmInfo = {
  tier?: string; model?: string; latency_ms?: number;
  difficulty?: number | string; status?: string; detail?: string; reason?: string;
};

function ChatResult({ data }: { data: ChatResponseT }) {
  const llm = data.llm as LlmInfo;
  const difficulty = typeof llm.difficulty === 'number' ? llm.difficulty : null;
  return (
    <div className="scan-result">
      <div className="scan-result-head">
        <span className={`pill pill-${data.decision}`}>{data.decision.toUpperCase()}</span>
        <span className="mono-muted">
          input {data.input_type} · router={data.router.strategy} · {data.latency_ms.toFixed(0)}ms
        </span>
      </div>

      <div className="llm-route-card" data-tier={llm.tier ?? 'none'}>
        <div className="llm-route-row">
          <span className={`pill ${llm.tier === 'big' ? 'pill-flag' : 'pill-allow'}`}>
            {llm.tier === 'big' ? 'BIG MODEL (paid API)' : llm.tier === 'local' ? 'LOCAL MODEL (free)' : 'NO LLM CALL'}
          </span>
          <span className="mono-muted">{llm.model ?? '—'} · {llm.latency_ms ?? '—'}ms</span>
        </div>
        {difficulty !== null && (
          <div className="llm-diff">
            <span className="mono-muted">difficulty {difficulty.toFixed(2)}</span>
            <div className="threat-bar" aria-hidden>
              <i style={{ width: `${Math.max(4, difficulty * 100)}%` }} />
            </div>
            <span className="mono-muted">{llm.reason ?? ''}</span>
          </div>
        )}
        {llm.status && llm.status !== 'ok' && (
          <p className="error-text">llm status: {llm.status}{llm.detail ? ` — ${llm.detail}` : ''}</p>
        )}
      </div>

      {data.decision === 'block' ? (
        <p className="muted-paragraph">Input was blocked by policy — nothing reached the model.</p>
      ) : data.answer ? (
        <div className="answer-box">
          <span className="data-label">Answer{data.output_guard.length > 0 ? ' — output guard flagged:' : ''}</span>
          <p className="answer-text">{data.answer}</p>
          {data.output_guard.map((g, i) => (
            <div key={i} className="detection-row">
              <span className="pill pill-redact">output guard · {g.detector} {g.score.toFixed(2)}</span>
              <span className="mono-muted">{g.explanation}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
