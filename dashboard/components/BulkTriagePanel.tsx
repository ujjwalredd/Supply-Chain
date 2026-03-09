"use client";

import { useRef, useState } from "react";
import { analyzeBulkStream, StreamUsage } from "@/lib/api";
import { Play, Square, Copy, Check } from "lucide-react";

const SEVERITY_OPTIONS = ["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const;

export function BulkTriagePanel() {
  const [severity, setSeverity] = useState<(typeof SEVERITY_OPTIONS)[number]>("CRITICAL");
  const [limit, setLimit] = useState(10);
  const [includeExecuted, setIncludeExecuted] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<StreamUsage | null>(null);
  const [copied, setCopied] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const run = async () => {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setStreaming(true);
    setText("");
    setError(null);
    setUsage(null);
    setCopied(false);
    try {
      await analyzeBulkStream(
        { severity_filter: severity, limit, include_executed: includeExecuted },
        (token) => setText((t) => t + token),
        { signal: ctrl.signal, onDone: (u) => setUsage(u) }
      );
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError((e as Error).message);
    } finally {
      setStreaming(false);
    }
  };

  const cancel = () => {
    abortRef.current?.abort();
    setStreaming(false);
  };

  const copy = async () => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  const sevColor =
    severity === "CRITICAL" ? "#ef4444"
    : severity === "HIGH" ? "#d97706"
    : severity === "MEDIUM" ? "#0070F3"
    : "#6b7280";

  return (
    <div className="glass-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="text-sm font-semibold text-foreground">Bulk AI Triage</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">
            Analyze all open deviations at once — Claude ranks priorities and surfaces root patterns
          </p>
        </div>
        {usage && (
          <span className="text-[10px] text-mutedForeground px-2 py-0.5 rounded bg-surfaceRaised border border-border">
            {(usage.input_tokens ?? 0) + (usage.output_tokens ?? 0)}t
            {usage.analysis_time_ms ? ` · ${(usage.analysis_time_ms / 1000).toFixed(1)}s` : ""}
          </span>
        )}
      </div>

      {/* Config strip */}
      <div className="px-5 py-3 border-b border-border flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground">Severity</span>
          <div className="flex gap-1">
            {SEVERITY_OPTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSeverity(s)}
                className="px-2 py-0.5 rounded text-[10px] font-semibold transition-colors"
                style={
                  severity === s
                    ? { background: `${sevColor}12`, color: sevColor, border: `1px solid ${sevColor}30` }
                    : { background: "transparent", color: "#94a3b8", border: "1px solid #e2e8f0" }
                }
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground">Limit</span>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="text-[12px] font-medium text-foreground rounded-lg px-2 py-1 bg-surfaceRaised border border-border focus:outline-none focus:ring-1 focus:ring-accent"
          >
            {[5, 10, 20, 50].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>

        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="checkbox"
            checked={includeExecuted}
            onChange={(e) => setIncludeExecuted(e.target.checked)}
            className="rounded accent-accent"
          />
          <span className="text-[11px] text-mutedForeground">Include executed</span>
        </label>

        <div className="ml-auto flex items-center gap-2">
          {!streaming && text && (
            <button
              type="button"
              onClick={copy}
              className="p-1.5 rounded-lg text-mutedForeground hover:text-foreground hover:bg-surfaceRaised transition-colors"
              aria-label="Copy"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          )}
          {!streaming ? (
            <button
              type="button"
              onClick={run}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-white text-xs font-medium transition-colors"
              style={{ background: sevColor }}
            >
              <Play className="h-3.5 w-3.5" />
              Analyze {severity}
            </button>
          ) : (
            <button
              type="button"
              onClick={cancel}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium border border-border hover:bg-surfaceRaised transition-colors"
            >
              <Square className="h-3.5 w-3.5" />
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* Output */}
      <div className="px-5 py-5 min-h-[200px]">
        {error && (
          <div
            className="p-3 rounded-lg"
            style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)" }}
          >
            <p className="text-xs font-medium text-destructive">Triage failed</p>
            <p className="text-[11px] text-mutedForeground mt-0.5">{error}</p>
            <button
              type="button"
              onClick={() => { setError(null); run(); }}
              className="mt-2 px-2.5 py-1 rounded-lg text-destructive text-[11px] font-medium"
              style={{ background: "rgba(239,68,68,0.08)" }}
            >
              Retry
            </button>
          </div>
        )}
        {!text && !error && !streaming && (
          <div className="flex flex-col items-center gap-3 py-10">
            <div
              className="h-10 w-10 rounded-xl flex items-center justify-center"
              style={{ background: `${sevColor}10`, border: `1px solid ${sevColor}20` }}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 1L10 6H15L11 9.5L13 15L8 11.5L3 15L5 9.5L1 6H6L8 1Z" stroke={sevColor} strokeWidth="1.2" strokeLinejoin="round"/>
              </svg>
            </div>
            <p className="text-xs text-mutedForeground text-center max-w-[240px]">
              Click <strong>Analyze {severity}</strong> to run Claude over all open {severity.toLowerCase()} deviations and get a prioritized action plan.
            </p>
          </div>
        )}
        {(text || streaming) && (
          <div className="rounded-lg p-4 bg-surfaceRaised border border-border">
            <p className="whitespace-pre-wrap font-sans text-[13px] leading-relaxed text-foreground">
              {text}
              {streaming && (
                <span className="inline-block w-1.5 h-[14px] ml-0.5 bg-accent animate-pulse align-middle" aria-hidden />
              )}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
