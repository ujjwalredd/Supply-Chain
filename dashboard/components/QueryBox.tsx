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
      className="rounded-xl overflow-hidden"
      style={{ background: "#111117", border: "1px solid rgba(124,106,247,0.2)" }}
    >
      {/* Header */}
      <div
        className="px-5 py-4 flex items-center justify-between"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
      >
        <div className="flex items-center gap-3">
          <div
            className="h-7 w-7 rounded-lg flex items-center justify-center shrink-0"
            style={{ background: "rgba(124,106,247,0.15)", border: "1px solid rgba(124,106,247,0.25)" }}
          >
            {/* Sparkle icon */}
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <path d="M6.5 1L7.5 5H11.5L8.5 7.5L9.5 11.5L6.5 9L3.5 11.5L4.5 7.5L1.5 5H5.5L6.5 1Z" stroke="#7c6af7" strokeWidth="1.1" strokeLinejoin="round"/>
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">Ask your supply chain</p>
            <p className="text-[11px] text-mutedForeground mt-0.5">Natural language queries answered with live data</p>
          </div>
        </div>
        {(answer || error) && (
          <button
            type="button"
            onClick={reset}
            className="text-[11px] text-mutedForeground hover:text-foreground transition-colors px-2.5 py-1 rounded"
            style={{ background: "rgba(255,255,255,0.05)" }}
          >
            Clear
          </button>
        )}
      </div>

      <div className="px-5 py-4 space-y-4">
        {/* Input row */}
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            placeholder="Which suppliers are at highest risk this week?"
            className="flex-1 rounded-lg px-3.5 py-2.5 text-sm text-foreground placeholder:text-mutedForeground outline-none transition-all"
            style={{
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.1)",
            }}
            onFocus={(e) => { (e.target as HTMLElement).style.borderColor = "rgba(124,106,247,0.5)"; }}
            onBlur={(e) => { (e.target as HTMLElement).style.borderColor = "rgba(255,255,255,0.1)"; }}
            onKeyDown={handleKeyDown}
            disabled={streaming}
          />
          <button
            type="button"
            onClick={() => submit(inputRef.current?.value ?? "")}
            disabled={streaming}
            className="shrink-0 px-4 py-2.5 rounded-lg text-white text-sm font-medium flex items-center gap-2 transition-all disabled:opacity-50"
            style={{ background: streaming ? "rgba(124,106,247,0.5)" : "#7c6af7" }}
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

        {/* Suggestion chips — hidden once answer is showing */}
        {!answer && !error && suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => handleSuggestion(s)}
                disabled={streaming}
                className="text-[11px] text-mutedForeground hover:text-foreground px-2.5 py-1 rounded-lg transition-colors disabled:opacity-50"
                style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}
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
            style={{ background: "rgba(248,113,113,0.08)", border: "1px solid rgba(248,113,113,0.2)", color: "#f87171" }}
          >
            {error}
          </div>
        )}

        {/* Answer */}
        {(answer || (streaming && !answer)) && (
          <div
            className="rounded-lg p-4"
            style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}
          >
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
              <p className="text-[10px] text-mutedForeground mt-3 pt-2.5" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                {(usage.input_tokens ?? 0) + (usage.output_tokens ?? 0)} tokens
                {usage.analysis_time_ms ? ` · ${(usage.analysis_time_ms / 1000).toFixed(1)}s` : ""}
                {" · "}<span style={{ color: "#7c6af7" }}>claude-sonnet-4-6</span>
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
