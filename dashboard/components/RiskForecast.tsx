"use client";

import { useEffect, useState } from "react";
import { fetchForecasts } from "@/lib/api";

type RiskRow = {
  order_id: string;
  supplier_id: string;
  days_to_delivery: number;
  risk_reason: string;
  alt_carrier?: string;
  alt_min_cost?: number;
  alt_transit_days?: number;
};

function urgencyColor(days: number) {
  if (days <= 1) return "#ef4444";
  if (days <= 3) return "#d97706";
  return "#64748b";
}

function urgencyBg(days: number) {
  if (days <= 1) return "rgba(239,68,68,0.06)";
  if (days <= 3) return "rgba(245,158,11,0.06)";
  return "transparent";
}

export function RiskForecast() {
  const [rows, setRows] = useState<RiskRow[]>([]);
  const [summary, setSummary] = useState<{ at_risk_count: number; suppliers_affected: number; avg_days_to_delivery: number | null } | null>(null);

  useEffect(() => {
    fetchForecasts({ limit: 20 })
      .then(setRows)
      .catch(() => setRows([]));
    fetch((process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000") + "/forecasts/summary")
      .then((r) => (r.ok ? r.json() : null))
      .then(setSummary)
      .catch(() => {});
  }, []);

  return (
    <div
      className="rounded-xl overflow-hidden bg-surface border border-border"
      style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}
    >
      <div className="px-5 py-4 flex items-center justify-between border-b border-border">
        <div>
          <p className="text-sm font-semibold text-foreground">Risk Forecast</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">Orders due within 7 days — sorted by urgency</p>
        </div>
        {summary && (
          <span className="text-[11px] text-mutedForeground">
            <span className="text-foreground font-semibold">{summary.at_risk_count}</span> at-risk
          </span>
        )}
      </div>
      <div className="overflow-y-auto max-h-[360px]">
        {rows.length === 0 && (
          <div className="px-5 py-10 text-center">
            <p className="text-xs text-mutedForeground">No at-risk orders. Run the Dagster pipeline to generate forecasts.</p>
          </div>
        )}
        {rows.map((r, idx) => {
          const col = urgencyColor(r.days_to_delivery);
          const bg = urgencyBg(r.days_to_delivery);
          return (
            <div
              key={r.order_id}
              className="flex items-stretch hover:bg-surfaceRaised transition-colors"
              style={{ borderBottom: idx < rows.length - 1 ? "1px solid #f1f5f9" : "none", background: bg }}
            >
              <div className="w-0.5 shrink-0" style={{ background: col }} />
              <div className="px-4 py-3.5 flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-xs font-medium text-foreground font-mono truncate">{r.order_id}</p>
                  <span className="text-[11px] font-semibold tabular-nums shrink-0 ml-4" style={{ color: col }}>
                    {r.days_to_delivery.toFixed(1)}d left
                  </span>
                </div>
                <p className="text-[11px] text-mutedForeground truncate">{r.risk_reason}</p>
                {r.alt_carrier && (
                  <p className="text-[10px] text-mutedForeground mt-1">
                    Alt: {r.alt_carrier} · ${r.alt_min_cost?.toFixed(0)} · {r.alt_transit_days}d
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
