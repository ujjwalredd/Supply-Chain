"use client";

import { useEffect, useState } from "react";
import { fetchCostAnalytics } from "@/lib/api";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type SupplierCost = {
  supplier_id: string;
  name: string;
  region: string;
  total_orders: number;
  total_spend: number;
  avg_order_value: number;
  delayed_count: number;
  delay_rate_pct: number;
  estimated_delay_cost_usd: number;
  cost_efficiency_score: number;
};

type View = "spend" | "delay_cost" | "efficiency";

const VIEW_OPTIONS: { key: View; label: string }[] = [
  { key: "spend", label: "Total Spend" },
  { key: "delay_cost", label: "Delay Cost" },
  { key: "efficiency", label: "Efficiency Score" },
];

function fmt(n: number) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

export function CostAnalyticsPanel() {
  const [data, setData] = useState<SupplierCost[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<View>("spend");

  useEffect(() => {
    setLoading(true);
    fetchCostAnalytics()
      .then((d) => setData(d.suppliers ?? []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, []);

  const totalSpend = data.reduce((s, r) => s + r.total_spend, 0);
  const totalDelayCost = data.reduce((s, r) => s + r.estimated_delay_cost_usd, 0);

  const chartData = data.slice(0, 8).map((r) => ({
    name: r.name.length > 12 ? r.name.slice(0, 12) + "…" : r.name,
    spend: r.total_spend,
    delay_cost: r.estimated_delay_cost_usd,
    efficiency: r.cost_efficiency_score,
    _full: r,
  }));

  const barKey = view === "spend" ? "spend" : view === "delay_cost" ? "delay_cost" : "efficiency";
  const barColor = view === "spend" ? "#0070F3" : view === "delay_cost" ? "#ef4444" : "#10b981";

  return (
    <div className="glass-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="text-sm font-semibold text-foreground">Cost Analytics</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">
            Supplier spend breakdown, delay cost exposure, and efficiency scores
          </p>
        </div>
        <div className="flex gap-1">
          {VIEW_OPTIONS.map((v) => (
            <button
              key={v.key}
              type="button"
              onClick={() => setView(v.key)}
              className="px-2.5 py-1 rounded text-[11px] font-medium transition-colors"
              style={
                view === v.key
                  ? { background: "rgba(0,112,243,0.08)", color: "#0070F3", border: "1px solid rgba(0,112,243,0.2)" }
                  : { background: "transparent", color: "#94a3b8", border: "1px solid #e2e8f0" }
              }
            >
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary strip */}
      <div className="grid grid-cols-3 divide-x divide-border border-b border-border">
        <div className="px-5 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground">Total Spend</p>
          <p className="text-xl font-bold tabular-nums text-foreground mt-0.5">{fmt(totalSpend)}</p>
        </div>
        <div className="px-5 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground">Delay Cost Exposure</p>
          <p className="text-xl font-bold tabular-nums mt-0.5" style={{ color: "#ef4444" }}>{fmt(totalDelayCost)}</p>
        </div>
        <div className="px-5 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground">Suppliers</p>
          <p className="text-xl font-bold tabular-nums text-foreground mt-0.5">{data.length}</p>
        </div>
      </div>

      {/* Chart */}
      <div className="px-4 py-5">
        {loading ? (
          <div className="h-[220px] flex items-center justify-center text-xs text-mutedForeground">Loading…</div>
        ) : chartData.length === 0 ? (
          <div className="h-[220px] flex items-center justify-center text-xs text-mutedForeground">No data</div>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" />
              <XAxis dataKey="name" tick={{ fontSize: 9, fill: "#94a3b8" }} />
              <YAxis
                tick={{ fontSize: 9, fill: "#94a3b8" }}
                tickFormatter={(v) =>
                  view === "efficiency" ? `${v}` : v >= 1000 ? `$${(v / 1000).toFixed(0)}K` : `$${v}`
                }
              />
              <Tooltip
                contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 11 }}
                formatter={(v: number) =>
                  view === "efficiency" ? [`${v.toFixed(1)}`, "Efficiency"] : [fmt(v), view === "spend" ? "Spend" : "Delay Cost"]
                }
              />
              <Bar dataKey={barKey} radius={[4, 4, 0, 0]}>
                {chartData.map((entry, i) => (
                  <Cell key={i} fill={barColor} opacity={0.8 + (i === 0 ? 0.2 : 0)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Table */}
      {!loading && data.length > 0 && (
        <div className="overflow-x-auto border-t border-border">
          <table className="w-full">
            <thead className="bg-surfaceRaised">
              <tr>
                {["Supplier", "Region", "Orders", "Total Spend", "Delay Cost", "Efficiency"].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((r, i) => (
                <tr key={r.supplier_id} style={{ borderTop: i > 0 ? "1px solid #f1f5f9" : undefined }}>
                  <td className="px-4 py-2.5 text-xs font-medium text-foreground">{r.name}</td>
                  <td className="px-4 py-2.5 text-[11px] text-mutedForeground">{r.region}</td>
                  <td className="px-4 py-2.5 text-xs tabular-nums text-foreground">{r.total_orders}</td>
                  <td className="px-4 py-2.5 text-xs tabular-nums font-medium text-foreground">{fmt(r.total_spend)}</td>
                  <td className="px-4 py-2.5 text-xs tabular-nums" style={{ color: r.estimated_delay_cost_usd > 0 ? "#ef4444" : "#94a3b8" }}>
                    {fmt(r.estimated_delay_cost_usd)}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 rounded-full bg-border overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${r.cost_efficiency_score}%`,
                            background: r.cost_efficiency_score >= 90 ? "#10b981" : r.cost_efficiency_score >= 70 ? "#f59e0b" : "#ef4444",
                          }}
                        />
                      </div>
                      <span className="text-[11px] tabular-nums font-medium" style={{ color: r.cost_efficiency_score >= 90 ? "#10b981" : r.cost_efficiency_score >= 70 ? "#d97706" : "#ef4444" }}>
                        {r.cost_efficiency_score.toFixed(0)}
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
