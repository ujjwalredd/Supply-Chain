"use client";

import { useEffect, useState } from "react";
import { fetchDelayPredictions } from "@/lib/api";

type Prediction = {
  order_id: string;
  supplier_id: string;
  supplier_name: string;
  product: string;
  order_value: number;
  status: string;
  expected_delivery: string | null;
  days_remaining: number;
  is_overdue: boolean;
  delay_probability: number;
  risk_level: "CRITICAL" | "HIGH" | "MEDIUM";
  supplier_trust: number;
  supplier_avg_delay_days: number;
};

const RISK_STYLE = {
  CRITICAL: { color: "#ef4444", bg: "rgba(239,68,68,0.08)", bar: "#ef4444" },
  HIGH:     { color: "#d97706", bg: "rgba(245,158,11,0.08)", bar: "#f59e0b" },
  MEDIUM:   { color: "#0070F3", bg: "rgba(0,112,243,0.08)", bar: "#0070F3" },
};

const MIN_PROB_OPTIONS = [0.3, 0.5, 0.7] as const;

function formatDelivery(iso: string | null, daysRemaining: number, isOverdue: boolean) {
  if (!iso) return "Unknown";
  const d = new Date(iso);
  const label = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  if (isOverdue) return `${label} (${Math.abs(daysRemaining)}d overdue)`;
  if (daysRemaining === 0) return `${label} (today)`;
  return `${label} (${daysRemaining}d)`;
}

export function ProactiveDelayPanel() {
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [minProb, setMinProb] = useState<(typeof MIN_PROB_OPTIONS)[number]>(0.3);

  useEffect(() => {
    setLoading(true);
    fetchDelayPredictions(25, minProb)
      .then((d) => setPredictions(d.predictions ?? []))
      .catch(() => setPredictions([]))
      .finally(() => setLoading(false));
  }, [minProb]);

  const critCount = predictions.filter((p) => p.risk_level === "CRITICAL").length;
  const highCount = predictions.filter((p) => p.risk_level === "HIGH").length;

  return (
    <div className="glass-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="text-sm font-semibold text-foreground">Proactive Delay Predictions</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">
            At-risk orders before they breach SLA — scored by trust, history, and lead time
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Summary chips */}
          {!loading && (
            <div className="flex gap-1.5">
              {critCount > 0 && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded" style={{ background: "rgba(239,68,68,0.08)", color: "#ef4444" }}>
                  {critCount} CRITICAL
                </span>
              )}
              {highCount > 0 && (
                <span className="text-[10px] font-bold px-2 py-0.5 rounded" style={{ background: "rgba(245,158,11,0.08)", color: "#d97706" }}>
                  {highCount} HIGH
                </span>
              )}
            </div>
          )}
          <select
            value={minProb}
            onChange={(e) => setMinProb(Number(e.target.value) as typeof minProb)}
            className="text-[12px] font-medium text-foreground rounded-lg px-3 py-1.5 bg-surfaceRaised border border-border focus:outline-none focus:ring-1 focus:ring-accent"
          >
            {MIN_PROB_OPTIONS.map((p) => (
              <option key={p} value={p}>≥{Math.round(p * 100)}% risk</option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="px-5 py-10 text-center text-xs text-mutedForeground">Scoring orders…</div>
      ) : predictions.length === 0 ? (
        <div className="px-5 py-10 text-center text-xs text-mutedForeground">
          No at-risk orders above {Math.round(minProb * 100)}% threshold
        </div>
      ) : (
        <div className="divide-y divide-border">
          {predictions.map((p) => {
            const style = RISK_STYLE[p.risk_level];
            const pctWidth = Math.round(p.delay_probability * 100);
            return (
              <div key={p.order_id} className="px-5 py-3.5 flex items-center gap-4">
                {/* Risk badge */}
                <span
                  className="text-[10px] font-bold px-2 py-0.5 rounded shrink-0 w-16 text-center"
                  style={{ background: style.bg, color: style.color }}
                >
                  {p.risk_level}
                </span>

                {/* Order info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] text-mutedForeground">{p.order_id}</span>
                    <span className="text-[11px] text-foreground font-medium truncate">{p.product}</span>
                  </div>
                  <p className="text-[11px] text-mutedForeground mt-0.5">
                    {p.supplier_name} · {formatDelivery(p.expected_delivery, p.days_remaining, p.is_overdue)}
                    {p.is_overdue && <span className="ml-1 font-semibold text-destructive">OVERDUE</span>}
                  </p>
                </div>

                {/* Probability bar */}
                <div className="w-28 shrink-0 hidden sm:block">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] text-mutedForeground">Delay risk</span>
                    <span className="text-[11px] font-bold tabular-nums" style={{ color: style.color }}>
                      {pctWidth}%
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-border overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${pctWidth}%`, background: style.bar }}
                    />
                  </div>
                </div>

                {/* Value */}
                <div className="text-right shrink-0 hidden md:block">
                  <p className="text-xs font-medium tabular-nums text-foreground">
                    ${p.order_value.toLocaleString()}
                  </p>
                  <p className="text-[10px] text-mutedForeground">
                    Trust {Math.round(p.supplier_trust * 100)}%
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
