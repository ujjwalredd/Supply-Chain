import { useCallback, useState, useRef } from "react";
import { motion } from "framer-motion";

export function QueryBox() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [usage, setUsage] = useState<{ input_tokens: number; output_tokens: number; analysis_time_ms: number } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const suggestions = [
    "Which suppliers are at highest risk?",
    "Show me the impact of Shanghai port delay",
    "How to mitigate semiconductor stockout?"
  ];

  const submit = useCallback(async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed || streaming) return;

    setQuestion(trimmed);
    setStreaming(true);
    setAnswer("");
    setUsage(null);

    // Simulate network delay
    await new Promise((r) => setTimeout(r, 600));

    // Fake intelligent response based on keywords
    let responseText = "Based on current medallion data lakes, everything is running smoothly. No critical deviations found in the supply chain graph.";
    
    if (trimmed.toLowerCase().includes("risk") || trimmed.toLowerCase().includes("supplier")) {
      responseText = "Analyzing live telemetry...\n\nI detect 14% deviation from baseline SLA for supplier GlobalFreight.\n\nRoot Cause: Port Congestion\nCalculated Risk: HIGH ($2.4M at risk)\n\nRecommendation: REROUTE to alternate suppliers with trust score ≥ 0.80.";
    } else if (trimmed.toLowerCase().includes("shanghai") || trimmed.toLowerCase().includes("delay")) {
      responseText = "The Shanghai port delay is currently tracking at 14 days above normal transit time.\n\nImpact Analysis:\n- Carrying Cost Impact: $240,000\n- Stockout Penalty Probability: 84%\n\nSuggested Action: Expedite critical SKUs via air freight to avoid downstream line stoppage.";
    } else if (trimmed.toLowerCase().includes("semiconductor")) {
      responseText = "Semiconductor inventory is currently at 4.2 days of supply (below 14-day safety threshold).\n\nAction taken: Autonomous escalation triggered. I have drafted an expedite order from the Taipei facility to cover the gap.";
    } else {
      responseText = "Processing recursive graph relationships...\n\nYour query did not match specific critical alerts. However, the overall network topology is functioning within standard mathematical bounds. Total active nodes: 19.";
    }

    // Stream the response word by word
    const words = responseText.split(" ");
    for (let i = 0; i < words.length; i++) {
      setAnswer((prev) => prev + (i === 0 ? "" : " ") + words[i]);
      // random delay between 20ms and 60ms
      await new Promise((r) => setTimeout(r, 20 + Math.random() * 40));
    }

    setStreaming(false);
    setUsage({
      input_tokens: 42 + Math.floor(Math.random() * 20),
      output_tokens: words.length * 1.5,
      analysis_time_ms: 1240 + Math.floor(Math.random() * 400),
    });

  }, [streaming]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") submit(e.currentTarget.value);
  };

  const handleSuggestion = (s: string) => {
    if (inputRef.current) inputRef.current.value = s;
    submit(s);
  };

  const reset = () => {
    setAnswer("");
    setUsage(null);
    setStreaming(false);
    setQuestion("");
    if (inputRef.current) inputRef.current.value = "";
    inputRef.current?.focus();
  };

  return (
    <div className="bg-white rounded-xl border border-black/5 shadow-sm overflow-hidden h-full flex flex-col">
      {/* Header */}
      <div className="px-6 py-4 border-b border-black/5 flex justify-between items-center bg-surface">
        <span className="text-sm font-semibold text-ink">Natural Language Query</span>
        {answer && !streaming && (
          <button
            type="button"
            onClick={reset}
            className="px-2 py-1 bg-white border border-black/5 hover:border-black/10 transition-colors rounded text-[10px] text-steel font-medium cursor-pointer"
          >
            Clear Conversation
          </button>
        )}
      </div>

      <div className="flex-1 flex flex-col p-6 overflow-hidden">
        {/* Input Area */}
        <div className="flex gap-2 shrink-0 mb-4">
          <input
            ref={inputRef}
            type="text"
            placeholder="Ask a question about the supply chain network..."
            className="flex-1 rounded-lg px-4 py-2.5 text-xs text-ink placeholder:text-steel/60 outline-none transition-all bg-white border border-black/10 focus:border-accent"
            onKeyDown={handleKeyDown}
            disabled={streaming}
          />
          <button
            type="button"
            onClick={() => submit(inputRef.current?.value ?? "")}
            disabled={streaming}
            className="shrink-0 px-6 py-2.5 rounded-lg text-white text-xs font-semibold flex items-center transition-all disabled:opacity-60 bg-ink hover:bg-black"
          >
            {streaming ? 'Asking...' : 'Ask AI'}
          </button>
        </div>

        {/* Suggestions */}
        {!answer && !streaming && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-wrap gap-2 shrink-0">
            {suggestions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => handleSuggestion(s)}
                disabled={streaming}
                className="text-[11px] text-steel hover:text-ink px-3 py-1.5 rounded bg-subtle border border-black/5 hover:border-black/10 transition-colors cursor-pointer text-left"
              >
                {s}
              </button>
            ))}
          </motion.div>
        )}

        {/* Answer Area */}
        {(answer || streaming) && (
          <motion.div 
            initial={{ opacity: 0, y: 5 }} 
            animate={{ opacity: 1, y: 0 }} 
            className="mt-2 rounded-lg p-5 bg-subtle border border-black/5 flex-1 overflow-y-auto"
          >
            {question && (
              <p className="text-xs text-steel font-medium mb-3">
                Query: <span className="italic text-ink">"{question}"</span>
              </p>
            )}
            
            <p className="text-sm text-ink leading-relaxed whitespace-pre-wrap">
              {answer || (
                <span className="text-steel">Processing query...</span>
              )}
              {streaming && (
                <span className="inline-block w-1.5 h-3.5 ml-1 bg-steel animate-pulse align-middle" aria-hidden />
              )}
            </p>

            {usage && !streaming && (
              <div className="mt-4 pt-4 border-t border-black/5 flex gap-3 text-[10px] text-steel font-mono">
                <span>Model: claude-sonnet-4.6</span>
                <span>Latency: {usage.analysis_time_ms}ms</span>
                <span>Tokens: {(usage.input_tokens + usage.output_tokens).toFixed(0)}</span>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
}
