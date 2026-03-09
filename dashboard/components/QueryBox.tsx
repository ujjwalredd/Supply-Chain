"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchQuerySuggestions, querySupplyChainStream, StreamUsage } from "@/lib/api";

export function QueryBox() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<StreamUsage | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchQuerySuggestions().then(setSuggestions).catch(() => {});
  }, []);

  const submit = useCallback(async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed || streaming) return;

    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setQuestion(trimmed);
    setStreaming(true);
    setAnswer("");
    setError(null);
    setUsage(null);

    try {
      await querySupplyChainStream(
        trimmed,
        (token) => setAnswer((a) => a + token),
        { signal: ctrl.signal, onDone: (u) => setUsage(u) }
      );
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError((e as Error).message);
      setAnswer("");
    } finally {
      setStreaming(false);
    }
  }, [streaming]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") submit(e.currentTarget.value);
  };

  const handleSuggestion = (s: string) => {
    if (inputRef.current) inputRef.current.value = s;
    submit(s);
  };

  const reset = () => {
    abortRef.current?.abort();
    setAnswer("");
    setError(null);
    setUsage(null);
    setStreaming(false);
    setQuestion("");
    if (inputRef.current) inputRef.current.value = "";
    inputRef.current?.focus();
  };

  return (
    <div
      className="rounded-xl overflow-hidden bg-surface"
      style={{ border: "1px solid rgba(99,102,241,0.2)", boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}
    >
      {/* Header */}
      <div className="px-5 py-4 flex items-center justify-between border-b border-border">
        <div className="flex items-center gap-3">
          <div
            className="h-8 w-8 rounded-lg flex items-center justify-center shrink-0"
            style={{ background: "rgba(99,102,241,0.08)", border: "1px solid rgba(99,102,241,0.15)" }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 1L8.2 5.5H13L9.5 8L10.8 12.5L7 10L3.2 12.5L4.5 8L1 5.5H5.8L7 1Z" stroke="#6366f1" strokeWidth="1.1" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">Ask your supply chain</p>
            <p className="text-[11px] text-mutedForeground mt-0.5">Natural language queries answered with live data via Claude</p>
          </div>
        </div>
        {(answer || error) && (
          <button
            type="button"
            onClick={reset}
            className="text-[11px] text-mutedForeground hover:text-foreground transition-colors px-2.5 py-1 rounded-lg bg-surfaceRaised border border-border"
          >
            Clear
          </button>
        )}
      </div>

      <div className="px-5 py-4 space-y-3">
        {/* Input row */}
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            placeholder="Which suppliers are at highest risk this week?"
            className="flex-1 rounded-lg px-3.5 py-2.5 text-sm text-foreground placeholder:text-mutedForeground outline-none transition-all bg-surfaceRaised border border-border focus:border-accent"
            onKeyDown={handleKeyDown}
            disabled={streaming}
          />
          <button
            type="button"
            onClick={() => submit(inputRef.current?.value ?? "")}
            disabled={streaming}
            className="shrink-0 px-4 py-2.5 rounded-lg text-white text-sm font-medium flex items-center gap-2 transition-all disabled:opacity-60"
            style={{ background: streaming ? "rgba(99,102,241,0.6)" : "#6366f1" }}
          >
            {streaming ? (
              <>
                <span className="inline-block h-3.5 w-3.5 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                <span className="hidden sm:inline">Thinking</span>
              </>
            ) : (
              <>
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <path d="M1.5 6.5H11.5M11.5 6.5L7.5 2.5M11.5 6.5L7.5 10.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                <span className="hidden sm:inline">Ask</span>
              </>
            )}
          </button>
        </div>

        {/* Suggestion chips */}
        {!answer && !error && suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => handleSuggestion(s)}
                disabled={streaming}
                className="text-[11px] text-mutedForeground hover:text-accent hover:border-accent/30 px-2.5 py-1 rounded-lg transition-colors disabled:opacity-50 bg-surfaceRaised border border-border"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Error */}
        {error && (
          <div
            className="rounded-lg p-3 text-xs"
            style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)", color: "#ef4444" }}
          >
            {error}
          </div>
        )}

        {/* Answer */}
        {(answer || (streaming && !answer)) && (
          <div className="rounded-lg p-4 bg-surfaceRaised border border-border">
            {question && (
              <p className="text-[11px] text-mutedForeground mb-2.5 italic truncate">
                &ldquo;{question}&rdquo;
              </p>
            )}
            <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
              {answer || (
                <span className="text-mutedForeground">Analyzing live data...</span>
              )}
              {streaming && (
                <span className="inline-block w-1.5 h-[14px] ml-0.5 bg-accent animate-pulse align-middle" aria-hidden />
              )}
            </p>
            {usage && !streaming && (
              <p className="text-[10px] text-mutedForeground mt-3 pt-2.5 border-t border-border">
                {(usage.input_tokens ?? 0) + (usage.output_tokens ?? 0)} tokens
                {usage.analysis_time_ms ? ` · ${(usage.analysis_time_ms / 1000).toFixed(1)}s` : ""}
                {" · "}<span style={{ color: "#6366f1" }}>claude-sonnet-4-6</span>
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
