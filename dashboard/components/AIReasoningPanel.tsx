"use client";

import { useCallback, useRef, useState } from "react";
import { analyzeDeviationStream, StreamUsage } from "@/lib/api";
import { X, Play, CheckCircle, AlertCircle, Square, Copy, Check } from "lucide-react";

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
  const abortRef = useRef<AbortController | null>(null);

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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ai-panel-title"
    >
      <div className="w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col rounded-lg border border-border bg-card shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <div>
            <p id="ai-panel-title" className="text-sm font-semibold text-foreground">
              AI Analysis
            </p>
            <p className="text-xs text-mutedForeground mt-0.5">
              {deviation.order_id} · {deviation.type} · {deviation.severity}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* Token usage badge */}
            {usage && (
              <span className="text-xs text-mutedForeground bg-muted px-2 py-0.5 rounded-full">
                {(usage.input_tokens ?? 0) + (usage.output_tokens ?? 0)} tokens
                {usage.analysis_time_ms ? ` · ${(usage.analysis_time_ms / 1000).toFixed(1)}s` : ""}
              </span>
            )}
            {/* Copy button — visible once analysis is done */}
            {!streaming && text && (
              <button
                type="button"
                onClick={copyText}
                className="p-1.5 rounded hover:bg-muted text-mutedForeground hover:text-foreground transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                aria-label="Copy analysis"
                title="Copy to clipboard"
              >
                {copied ? (
                  <Check className="h-4 w-4 text-success" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded hover:bg-muted text-mutedForeground hover:text-foreground transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 p-5">
          {error && (
            <div
              className="mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/30 flex items-start gap-3"
              role="alert"
            >
              <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-destructive">Analysis failed</p>
                <p className="text-xs text-mutedForeground mt-1 break-words">{error}</p>
                <button
                  type="button"
                  onClick={() => { setError(null); startAnalysis(); }}
                  className="mt-2 px-3 py-1.5 rounded bg-destructive/20 text-destructive text-xs font-medium hover:bg-destructive/30 transition-colors"
                >
                  Retry
                </button>
              </div>
            </div>
          )}

          {!streaming && !text && !error && (
            <div className="flex flex-col items-center gap-5 py-10">
              <p className="text-sm text-mutedForeground text-center max-w-sm">
                Run Claude&apos;s analysis to get a trade-off recommendation for this deviation.
              </p>
              <button
                type="button"
                onClick={startAnalysis}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent/90 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                <Play className="h-3.5 w-3.5" />
                Run Analysis
              </button>
            </div>
          )}

          {(streaming || text) && (
            <div className="space-y-4">
              <div className="rounded-lg bg-background border border-border p-4">
                <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground">
                  {text}
                  {streaming && (
                    <span
                      className="inline-block w-1.5 h-4 ml-0.5 bg-accent animate-pulse align-middle"
                      aria-hidden
                    />
                  )}
                </pre>
              </div>

              <div className="flex items-center gap-3">
                {streaming && (
                  <button
                    type="button"
                    onClick={cancelAnalysis}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-mutedForeground text-sm font-medium hover:bg-muted hover:text-foreground transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  >
                    <Square className="h-3.5 w-3.5" />
                    Cancel
                  </button>
                )}
                {!streaming && text && (
                  <button
                    type="button"
                    onClick={onExecute}
                    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-success/90 text-white text-sm font-medium hover:bg-success transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-success"
                  >
                    <CheckCircle className="h-3.5 w-3.5" />
                    Execute Recommendation
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
