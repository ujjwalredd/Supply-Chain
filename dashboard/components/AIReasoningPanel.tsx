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
    // Cancel any in-flight request
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
      if ((e as Error).name === "AbortError") return; // user cancelled
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

  return (
    <>
      {/* Backdrop — click to close */}
      <div
        className="fixed inset-0 z-40 bg-black/40"
        onClick={onClose}
        aria-hidden
      />

      {/* Right-side drawer */}
      <div
        className="fixed right-0 top-0 bottom-0 z-50 flex flex-col w-full max-w-[420px]"
        style={{ background: "#111117", borderLeft: "1px solid rgba(255,255,255,0.08)" }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="ai-panel-title"
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3 shrink-0"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
        >
          <div className="min-w-0">
            <p id="ai-panel-title" className="text-sm font-semibold text-foreground">
              AI Analysis
            </p>
            <p className="text-[11px] text-mutedForeground mt-0.5 truncate">
              {deviation.order_id} · <span className="uppercase">{deviation.type}</span> · {deviation.severity}
            </p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0 ml-3">
            {usage && (
              <span
                className="text-[10px] text-mutedForeground px-2 py-0.5 rounded"
                style={{ background: "rgba(255,255,255,0.06)" }}
              >
                {(usage.input_tokens ?? 0) + (usage.output_tokens ?? 0)}t
                {usage.analysis_time_ms ? ` · ${(usage.analysis_time_ms / 1000).toFixed(1)}s` : ""}
              </span>
            )}
            {!streaming && text && (
              <button
                type="button"
                onClick={copyText}
                className="p-1.5 rounded text-mutedForeground hover:text-foreground transition-colors"
                style={{ background: "transparent" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.06)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
                aria-label="Copy analysis"
                title="Copy to clipboard"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded text-mutedForeground hover:text-foreground transition-colors"
              style={{ background: "transparent" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.06)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
              aria-label="Close"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Body — scrollable */}
        <div className="overflow-y-auto flex-1 px-4 py-4 space-y-4">
          {error && (
            <div
              className="p-3 rounded-lg flex items-start gap-3"
              style={{ background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.2)" }}
              role="alert"
            >
              <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-destructive">Analysis failed</p>
                <p className="text-[11px] text-mutedForeground mt-0.5 break-words">{error}</p>
                <button
                  type="button"
                  onClick={() => { setError(null); startAnalysis(); }}
                  className="mt-2 px-2.5 py-1 rounded text-destructive text-[11px] font-medium transition-colors"
                  style={{ background: "rgba(248,113,113,0.15)" }}
                >
                  Retry
                </button>
              </div>
            </div>
          )}

          {!streaming && !text && !error && (
            <div className="flex flex-col items-center gap-4 py-12">
              <p className="text-xs text-mutedForeground text-center max-w-[280px]">
                Run Claude&apos;s analysis for root cause, financial impact, and trade-off options.
              </p>
              <button
                type="button"
                onClick={startAnalysis}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-medium transition-colors"
                style={{ background: "#7c6af7" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "#6b5ce7"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "#7c6af7"; }}
              >
                <Play className="h-3.5 w-3.5" />
                Run Analysis
              </button>
            </div>
          )}

          {(streaming || text) && (
            <>
              <div
                className="rounded-lg p-3"
                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}
              >
                <p className="whitespace-pre-wrap font-sans text-[13px] leading-relaxed text-foreground">
                  {text}
                  {streaming && (
                    <span
                      className="inline-block w-1.5 h-[14px] ml-0.5 bg-accent animate-pulse align-middle"
                      aria-hidden
                    />
                  )}
                </p>
              </div>

              <div className="flex items-center gap-2">
                {streaming && (
                  <button
                    type="button"
                    onClick={cancelAnalysis}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-mutedForeground text-xs font-medium transition-colors"
                    style={{ border: "1px solid rgba(255,255,255,0.1)" }}
                  >
                    <Square className="h-3 w-3" />
                    Cancel
                  </button>
                )}
                {!streaming && text && (
                  <button
                    type="button"
                    onClick={onExecute}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-white text-xs font-medium transition-colors"
                    style={{ background: "rgba(52,211,153,0.9)" }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "#34d399"; }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(52,211,153,0.9)"; }}
                  >
                    <CheckCircle className="h-3 w-3" />
                    Execute Recommendation
                  </button>
                )}
              </div>
            </>
          )}

          {/* Ontology Constraints Applied */}
          {constraints.length > 0 && (
            <div className="pt-3" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
              <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-mutedForeground mb-2">
                Rules Applied
              </p>
              <div className="flex flex-wrap gap-1.5">
                {constraints.map((c) => (
                  <span
                    key={c.id}
                    title={`${c.constraint_type}: ${c.value}${c.hard_limit ? " (hard limit)" : ""}`}
                    className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium"
                    style={{
                      background: c.hard_limit ? "rgba(248,113,113,0.08)" : "rgba(124,106,247,0.08)",
                      color: c.hard_limit ? "#f87171" : "#7c6af7",
                      border: `1px solid ${c.hard_limit ? "rgba(248,113,113,0.2)" : "rgba(124,106,247,0.2)"}`,
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
