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

function urgencyColor(days: number): string {
  if (days <= 1) return "text-destructive";
  if (days <= 3) return "text-warning";
  return "text-mutedForeground";
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
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <p className="text-sm font-medium text-foreground">Risk Forecast</p>
        <p className="text-xs text-mutedForeground">
          {summary ? `${summary.at_risk_count} at-risk · ${summary.suppliers_affected} suppliers` : "orders due ≤7 days"}
        </p>
      </div>
      <div className="divide-y divide-border max-h-[320px] overflow-y-auto">
        {rows.length === 0 && (
          <p className="text-xs text-mutedForeground px-4 py-6">
            No at-risk orders detected. Run the pipeline to generate forecasts.
          </p>
        )}
        {rows.map((r) => (
          <div key={r.order_id} className="px-4 py-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-foreground truncate">{r.order_id}</p>
              <span className={`text-xs font-medium tabular-nums shrink-0 ml-4 ${urgencyColor(r.days_to_delivery)}`}>
                {r.days_to_delivery.toFixed(1)}d left
              </span>
            </div>
            <p className="text-xs text-mutedForeground mt-0.5 truncate">{r.risk_reason}</p>
            {r.alt_carrier && (
              <p className="text-xs text-mutedForeground mt-1">
                Alt: {r.alt_carrier} · ${r.alt_min_cost?.toFixed(0)} · {r.alt_transit_days}d
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
