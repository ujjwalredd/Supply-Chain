"use client";

import { useCallback, useEffect, useState } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { fetchAlerts, dismissAlert } from "@/lib/api";
import { AIReasoningPanel } from "@/components/AIReasoningPanel";

type Deviation = {
  deviation_id: string;
  order_id: string;
  type: string;
  severity: string;
  detected_at: string;
  ai_analysis?: unknown;
  recommended_action?: string;
  executed: boolean;
};

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const SEV: Record<string, { color: string; dot: string; text: string }> = {
  CRITICAL: { color: "#f87171", dot: "bg-destructive",   text: "text-destructive" },
  HIGH:     { color: "#fbbf24", dot: "bg-warning",       text: "text-warning" },
  MEDIUM:   { color: "#7c6af7", dot: "bg-accent",        text: "text-accent" },
};

const SEVERITIES = ["ALL", "CRITICAL", "HIGH", "MEDIUM"] as const;
type SeverityFilter = typeof SEVERITIES[number];

export function DeviationFeed() {
  const [deviations, setDeviations] = useState<Deviation[]>([]);
  const [selected, setSelected] = useState<Deviation | null>(null);
  const [sevFilter, setSevFilter] = useState<SeverityFilter>("ALL");

  const loadAlerts = useCallback(async () => {
    try {
      const data = await fetchAlerts({ limit: 50, executed: false });
      setDeviations(data);
    } catch {
      setDeviations([]);
    }
  }, []);

  useWebSocket((msg) => {
    if (msg.type === "deviation" && msg.data) {
      setDeviations((prev) => [msg.data as Deviation, ...prev]);
    }
  });

  useEffect(() => {
    loadAlerts();
    const id = setInterval(loadAlerts, 10000);
    return () => clearInterval(id);
  }, [loadAlerts]);

  const handleExecute = async (d: Deviation) => {
    try {
      await dismissAlert(d.deviation_id);
      setDeviations((prev) =>
        prev.map((x) => (x.deviation_id === d.deviation_id ? { ...x, executed: true } : x))
      );
      setSelected(null);
    } catch {}
  };

  const allActive = deviations.filter((d) => !d.executed);
  const active = sevFilter === "ALL" ? allActive : allActive.filter((d) => d.severity === sevFilter);

  return (
    <>
      <div className="rounded-xl overflow-hidden flex flex-col" style={{ background: "#111117", border: "1px solid rgba(255,255,255,0.07)" }}>
        {/* Header */}
        <div className="px-5 py-4 flex items-center justify-between" style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}>
          <div>
            <p className="text-sm font-semibold text-foreground">Deviations</p>
            <p className="text-[11px] text-mutedForeground mt-0.5">Active supply chain alerts</p>
          </div>
          {allActive.length > 0 && (
            <span className="text-[11px] font-semibold tabular-nums px-2 py-0.5 rounded-md" style={{ background: "rgba(248,113,113,0.1)", color: "#f87171" }}>
              {allActive.length} active
            </span>
          )}
        </div>

        {/* Severity filter tabs */}
        <div className="flex gap-1 px-5 py-2.5" style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
          {SEVERITIES.map((sev) => {
            const isActive = sevFilter === sev;
            const sevColor = sev === "CRITICAL" ? "#f87171" : sev === "HIGH" ? "#fbbf24" : sev === "MEDIUM" ? "#7c6af7" : "#a0a0b0";
            return (
              <button
                key={sev}
                type="button"
                onClick={() => setSevFilter(sev)}
                className="px-2.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide transition-colors"
                style={{
                  background: isActive ? (sev === "ALL" ? "rgba(255,255,255,0.1)" : `${sevColor}22`) : "transparent",
                  color: isActive ? (sev === "ALL" ? "#e0e0f0" : sevColor) : "rgba(160,160,176,0.6)",
                  border: `1px solid ${isActive ? (sev === "ALL" ? "rgba(255,255,255,0.15)" : `${sevColor}44`) : "transparent"}`,
                }}
              >
                {sev}
              </button>
            );
          })}
        </div>

        {/* List */}
        <div className="overflow-y-auto max-h-[360px]">
          {active.length === 0 && (
            <div className="px-5 py-10 text-center">
              <div className="h-8 w-8 rounded-full mx-auto mb-3 flex items-center justify-center" style={{ background: "rgba(52,211,153,0.1)" }}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M2.5 7L5.5 10L11.5 4" stroke="#34d399" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <p className="text-xs text-mutedForeground">No active deviations</p>
            </div>
          )}
          {active.map((d, idx) => {
            const sev = SEV[d.severity] ?? SEV.MEDIUM;
            return (
              <button
                key={d.deviation_id}
                type="button"
                onClick={() => setSelected(d)}
                className="w-full text-left group transition-colors"
                style={{ background: "transparent", borderBottom: idx < active.length - 1 ? "1px solid rgba(255,255,255,0.05)" : "none" }}
                onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.02)"; }}
                onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
              >
                <div className="flex items-stretch">
                  {/* Severity bar */}
                  <div className="w-0.5 shrink-0 my-0 rounded-r-full" style={{ background: sev.color }} />
                  <div className="flex items-center justify-between px-4 py-3.5 w-full min-w-0">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-[10px] font-bold uppercase tracking-widest ${sev.text}`}>
                          {d.severity}
                        </span>
                        <span className="text-[11px] text-mutedForeground">{d.type}</span>
                      </div>
                      <p className="text-sm font-medium text-foreground truncate font-mono">{d.order_id}</p>
                    </div>
                    <span className="text-[11px] text-mutedForeground shrink-0 ml-4 group-hover:text-foreground transition-colors">
                      {relativeTime(d.detected_at)}
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {selected && (
        <AIReasoningPanel
          deviation={selected}
          onClose={() => setSelected(null)}
          onExecute={() => handleExecute(selected)}
        />
      )}
    </>
  );
}
