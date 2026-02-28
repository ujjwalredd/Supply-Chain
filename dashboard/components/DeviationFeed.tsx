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

const severityColor: Record<string, string> = {
  CRITICAL: "text-destructive",
  HIGH: "text-warning",
  MEDIUM: "text-mutedForeground",
};

export function DeviationFeed() {
  const [deviations, setDeviations] = useState<Deviation[]>([]);
  const [selected, setSelected] = useState<Deviation | null>(null);

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

  return (
    <>
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        <div className="px-4 py-3 border-b border-border">
          <p className="text-sm font-medium text-foreground">Deviations</p>
        </div>
        <div className="divide-y divide-border max-h-[340px] overflow-y-auto">
          {deviations.length === 0 && (
            <p className="text-xs text-mutedForeground px-4 py-6">No active deviations.</p>
          )}
          {deviations.map((d) => (
            <button
              key={d.deviation_id}
              type="button"
              onClick={() => setSelected(d)}
              className={`w-full flex items-center justify-between px-4 py-3 text-left hover:bg-muted transition-colors ${d.executed ? "opacity-50" : ""}`}
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{d.order_id}</p>
                <p className={`text-xs mt-0.5 ${severityColor[d.severity] ?? "text-mutedForeground"}`}>
                  {d.type} · {d.severity}
                </p>
              </div>
              <span className="text-xs text-mutedForeground shrink-0 ml-4">
                {relativeTime(d.detected_at)}
              </span>
            </button>
          ))}
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
