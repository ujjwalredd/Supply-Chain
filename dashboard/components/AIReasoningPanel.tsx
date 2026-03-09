"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { analyzeDeviationStream, fetchOntologyConstraints, StreamUsage } from "@/lib/api";
import { X, Play, CheckCircle, AlertCircle, Square, Copy, Check } from "lucide-react";

type Constraint = {
  id: number;
  entity_id: string;
  constraint_type: string;
  value: number;
  hard_limit: boolean;
};

type Deviation = {
  deviation_id: string;
  order_id: string;
  type: string;
  severity: string;
};

export function AIReasoningPanel({
  deviation,
  onClose,
  onExecute,
}: {
  deviation: Deviation;
  onClose: () => void;
  onExecute: () => void;
}) {
  const [streaming, setStreaming] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<StreamUsage | null>(null);
  const [copied, setCopied] = useState(false);
  const [constraints, setConstraints] = useState<Constraint[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    fetchOntologyConstraints()
      .then(setConstraints)
      .catch(() => setConstraints([]));
  }, []);

  const startAnalysis = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStreaming(true);
    setText("");
    setError(null);
    setUsage(null);
    setCopied(false);

    try {
      await analyzeDeviationStream(
        {
          deviation_id: deviation.deviation_id,
          order_id: deviation.order_id,
          deviation_type: deviation.type,
          severity: deviation.severity,
        },
        (token) => setText((t) => t + token),
        {
          signal: controller.signal,
          onDone: (u) => setUsage(u),
        }
      );
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      const msg = (e as Error).message;
      setError(msg);
      setText("");
    } finally {
      setStreaming(false);
    }
  }, [deviation]);

  const cancelAnalysis = useCallback(() => {
    abortRef.current?.abort();
    setStreaming(false);
  }, []);

  const copyText = useCallback(async () => {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  }, [text]);

  const sevColor =
    deviation.severity === "CRITICAL" ? "#ef4444"
    : deviation.severity === "HIGH" ? "#d97706"
    : "#0070F3";

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[2px]" onClick={onClose} aria-hidden />

      {/* Right-side drawer */}
      <div
        className="fixed right-0 top-0 bottom-0 z-50 flex flex-col w-full max-w-[440px] bg-surface"
        style={{ borderLeft: "1px solid #e2e8f0", boxShadow: "-4px 0 24px rgba(0,0,0,0.08)" }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ai-panel-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 shrink-0 border-b border-border">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span
                className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold uppercase"
                style={{ background: `${sevColor}12`, color: sevColor }}
              >
                {deviation.severity}
              </span>
              <span className="text-[11px] text-mutedForeground uppercase">{deviation.type.replace(/_/g, " ")}</span>
            </div>
            <p id="ai-panel-title" className="text-sm font-semibold text-foreground font-mono truncate">
              {deviation.order_id}
            </p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0 ml-3">
            {usage && (
              <span className="text-[10px] text-mutedForeground px-2 py-0.5 rounded bg-surfaceRaised border border-border">
                {(usage.input_tokens ?? 0) + (usage.output_tokens ?? 0)}t
                {usage.analysis_time_ms ? ` · ${(usage.analysis_time_ms / 1000).toFixed(1)}s` : ""}
              </span>
            )}
            {!streaming && text && (
              <button
                type="button"
                onClick={copyText}
                className="p-1.5 rounded-lg text-mutedForeground hover:text-foreground hover:bg-surfaceRaised transition-colors"
                aria-label="Copy analysis"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-mutedForeground hover:text-foreground hover:bg-surfaceRaised transition-colors"
              aria-label="Close"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-5 py-5 space-y-4">
          {error && (
            <div
              className="p-3 rounded-lg flex items-start gap-3"
              style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)" }}
              role="alert"
            >
              <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-destructive">Analysis failed</p>
                <p className="text-[11px] text-mutedForeground mt-0.5 break-words">{error}</p>
                <button
                  type="button"
                  onClick={() => { setError(null); startAnalysis(); }}
                  className="mt-2 px-2.5 py-1 rounded-lg text-destructive text-[11px] font-medium transition-colors"
                  style={{ background: "rgba(239,68,68,0.08)" }}
                >
                  Retry
                </button>
              </div>
            </div>
          )}

          {!streaming && !text && !error && (
            <div className="flex flex-col items-center gap-4 py-14">
              <div
                className="h-12 w-12 rounded-xl flex items-center justify-center"
                style={{ background: "rgba(0,112,243,0.08)", border: "1px solid rgba(0,112,243,0.15)" }}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M10 2L12 8H18L13 12L15 18L10 14L5 18L7 12L2 8H8L10 2Z" stroke="#0070F3" strokeWidth="1.3" strokeLinejoin="round"/>
                </svg>
              </div>
              <div className="text-center">
                <p className="text-sm font-medium text-foreground">AI Deviation Analysis</p>
                <p className="text-xs text-mutedForeground mt-1 max-w-[260px]">
                  Root cause, financial impact, and trade-off options powered by Claude
                </p>
              </div>
              <button
                type="button"
                onClick={startAnalysis}
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-white text-sm font-medium transition-colors"
                style={{ background: "#0070F3" }}
              >
                <Play className="h-3.5 w-3.5" />
                Run Analysis
              </button>
            </div>
          )}

          {(streaming || text) && (
            <>
              <div className="rounded-lg p-4 bg-surfaceRaised border border-border">
                <p className="whitespace-pre-wrap font-sans text-[13px] leading-relaxed text-foreground">
                  {text}
                  {streaming && (
                    <span className="inline-block w-1.5 h-[14px] ml-0.5 bg-accent animate-pulse align-middle" aria-hidden />
                  )}
                </p>
              </div>

              <div className="flex items-center gap-2">
                {streaming && (
                  <button
                    type="button"
                    onClick={cancelAnalysis}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-mutedForeground text-xs font-medium transition-colors border border-border hover:bg-surfaceRaised"
                  >
                    <Square className="h-3 w-3" />
                    Cancel
                  </button>
                )}
                {!streaming && text && (
                  <>
                    <button
                      type="button"
                      onClick={startAnalysis}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-mutedForeground text-xs font-medium transition-colors border border-border hover:bg-surfaceRaised"
                    >
                      <Play className="h-3 w-3" />
                      Re-run
                    </button>
                    <button
                      type="button"
                      onClick={onExecute}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-white text-xs font-medium transition-colors"
                      style={{ background: "#10b981" }}
                    >
                      <CheckCircle className="h-3 w-3" />
                      Execute Recommendation
                    </button>
                  </>
                )}
              </div>
            </>
          )}

          {/* Ontology Constraints */}
          {constraints.length > 0 && (
            <div className="pt-4 border-t border-border">
              <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-mutedForeground mb-2">
                Business Rules Applied
              </p>
              <div className="flex flex-wrap gap-1.5">
                {constraints.map((c) => (
                  <span
                    key={c.id}
                    title={`${c.constraint_type}: ${c.value}${c.hard_limit ? " (hard limit)" : ""}`}
                    className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium"
                    style={{
                      background: c.hard_limit ? "rgba(239,68,68,0.06)" : "rgba(0,112,243,0.06)",
                      color: c.hard_limit ? "#ef4444" : "#0070F3",
                      border: `1px solid ${c.hard_limit ? "rgba(239,68,68,0.15)" : "rgba(0,112,243,0.15)"}`,
                    }}
                  >
                    {c.constraint_type.replace(/_/g, " ").toLowerCase()} &le; {c.value}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
