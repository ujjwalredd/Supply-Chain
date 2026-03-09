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

const SEV: Record<string, { color: string; bg: string; text: string; label: string }> = {
  CRITICAL: { color: "#ef4444", bg: "rgba(239,68,68,0.08)",  text: "#ef4444",  label: "Critical" },
  HIGH:     { color: "#f59e0b", bg: "rgba(245,158,11,0.08)", text: "#d97706",  label: "High" },
  MEDIUM:   { color: "#0070F3", bg: "rgba(0,112,243,0.08)",  text: "#0070F3",  label: "Medium" },
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
      <div className="rounded-xl overflow-hidden bg-surface border border-border" style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}>
        {/* Header */}
        <div className="px-5 py-4 flex items-center justify-between border-b border-border">
          <div>
            <p className="text-sm font-semibold text-foreground">Active Deviations</p>
            <p className="text-[11px] text-mutedForeground mt-0.5">Click any row to trigger AI analysis</p>
          </div>
          {allActive.length > 0 && (
            <span
              className="text-[11px] font-semibold tabular-nums px-2.5 py-1 rounded-full"
              style={{ background: "rgba(239,68,68,0.08)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.15)" }}
            >
              {allActive.length} active
            </span>
          )}
        </div>

        {/* Severity filter tabs */}
        <div className="flex gap-1.5 px-5 py-2.5 border-b border-border bg-surfaceRaised">
          {SEVERITIES.map((sev) => {
            const isActive = sevFilter === sev;
            const sevColor =
              sev === "CRITICAL" ? "#ef4444"
              : sev === "HIGH" ? "#d97706"
              : sev === "MEDIUM" ? "#0070F3"
              : "#64748b";
            return (
              <button
                key={sev}
                type="button"
                onClick={() => setSevFilter(sev)}
                className="px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all"
                style={{
                  background: isActive
                    ? sev === "ALL" ? "rgba(15,23,42,0.07)" : `${sevColor}14`
                    : "transparent",
                  color: isActive ? (sev === "ALL" ? "#0f172a" : sevColor) : "#94a3b8",
                  border: `1px solid ${isActive ? (sev === "ALL" ? "rgba(15,23,42,0.12)" : `${sevColor}30`) : "transparent"}`,
                }}
              >
                {sev === "ALL" ? "All" : sev === "CRITICAL" ? "Critical" : sev === "HIGH" ? "High" : "Medium"}
              </button>
            );
          })}
        </div>

        {/* List */}
        <div className="overflow-y-auto max-h-[400px]">
          {active.length === 0 && (
            <div className="px-5 py-12 text-center">
              <div
                className="h-10 w-10 rounded-full mx-auto mb-3 flex items-center justify-center"
                style={{ background: "rgba(16,185,129,0.08)" }}
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M3 8L6.5 11.5L13 5" stroke="#10b981" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <p className="text-sm font-medium text-foreground">All clear</p>
              <p className="text-[11px] text-mutedForeground mt-1">No active deviations</p>
            </div>
          )}
          {active.map((d, idx) => {
            const sev = SEV[d.severity] ?? SEV.MEDIUM;
            return (
              <button
                key={d.deviation_id}
                type="button"
                onClick={() => setSelected(d)}
                className="w-full text-left transition-colors hover:bg-surfaceRaised"
                style={{ borderBottom: idx < active.length - 1 ? "1px solid #f1f5f9" : "none" }}
              >
                <div className="flex items-stretch">
                  <div className="w-0.5 shrink-0" style={{ background: sev.color }} />
                  <div className="flex items-center justify-between px-4 py-3.5 w-full min-w-0">
                    <div className="min-w-0 flex items-center gap-3">
                      <span
                        className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider shrink-0"
                        style={{ background: sev.bg, color: sev.text }}
                      >
                        {sev.label}
                      </span>
                      <div className="min-w-0">
                        <p className="text-[11px] font-medium text-foreground font-mono truncate">{d.order_id}</p>
                        <p className="text-[10px] text-mutedForeground mt-0.5">{d.type.replace(/_/g, " ")}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0 ml-4">
                      <span className="text-[10px] text-mutedForeground">{relativeTime(d.detected_at)}</span>
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="text-mutedForeground">
                        <path d="M4.5 2.5L8 6L4.5 9.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
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
