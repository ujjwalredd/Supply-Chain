"use client";

import { useEffect, useState } from "react";
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchSupplierScorecard, fetchSuppliers } from "@/lib/api";

type Supplier = { supplier_id: string; name: string; region: string; trust_score: number };
type Week = {
  week: string;
  total_orders: number;
  on_time_pct: number | null;
  avg_delay_days: number;
  deviation_count: number;
};
type Scorecard = {
  supplier: {
    supplier_id: string;
    name: string;
    region: string;
    trust_score: number;
    total_orders: number;
    delayed_orders: number;
    avg_delay_days: number;
    delay_rate_pct: number;
  };
  weeks: Week[];
};

const WEEK_OPTIONS = [8, 12, 24, 52] as const;

const CustomTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ dataKey: string; color: string; value: number | null }>; label?: string }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-surface border border-border rounded-xl px-3 py-2.5 text-xs shadow-lg">
      <p className="font-semibold text-foreground mb-1.5">Week of {label}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
            <span className="text-mutedForeground">{p.dataKey}</span>
          </span>
          <span className="font-semibold tabular-nums" style={{ color: p.color }}>
            {p.value == null ? "—" : p.dataKey === "On-Time %" ? `${p.value}%` : p.value}
          </span>
        </div>
      ))}
    </div>
  );
};

export function SupplierScorecard() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [weeks, setWeeks] = useState<(typeof WEEK_OPTIONS)[number]>(12);
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchSuppliers({ limit: 100 })
      .then((s) => {
        setSuppliers(s);
        if (s.length > 0) setSelectedId(s[0].supplier_id);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    fetchSupplierScorecard(selectedId, weeks)
      .then(setScorecard)
      .catch(() => setScorecard(null))
      .finally(() => setLoading(false));
  }, [selectedId, weeks]);

  const chartData = (scorecard?.weeks ?? []).map((w) => ({
    week: w.week.slice(5),
    "On-Time %": w.on_time_pct,
    "Delay (d)": w.avg_delay_days,
    Deviations: w.deviation_count,
    orders: w.total_orders,
  }));

  const hasData = chartData.some((d) => d.orders > 0);
  const s = scorecard?.supplier;
  const trustColor = s
    ? s.trust_score >= 0.85 ? "#10b981" : s.trust_score >= 0.7 ? "#f59e0b" : "#ef4444"
    : "#94a3b8";

  return (
    <div className="space-y-5">
      <div className="glass-card overflow-hidden">
        {/* Header + controls */}
        <div className="px-5 py-4 border-b border-border flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-sm font-semibold text-foreground">Supplier Scorecard</p>
            <p className="text-[11px] text-mutedForeground mt-0.5">
              Weekly performance — on-time rate (left), delays &amp; deviations (right)
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="text-[12px] font-medium text-foreground rounded-lg px-3 py-1.5 bg-surfaceRaised border border-border focus:outline-none focus:ring-1 focus:ring-accent"
            >
              {suppliers.map((sup) => (
                <option key={sup.supplier_id} value={sup.supplier_id}>
                  {sup.name} ({sup.supplier_id})
                </option>
              ))}
            </select>
            <select
              value={weeks}
              onChange={(e) => setWeeks(Number(e.target.value) as typeof weeks)}
              className="text-[12px] font-medium text-foreground rounded-lg px-3 py-1.5 bg-surfaceRaised border border-border focus:outline-none focus:ring-1 focus:ring-accent"
            >
              {WEEK_OPTIONS.map((w) => (
                <option key={w} value={w}>{w}w</option>
              ))}
            </select>
          </div>
        </div>

        {/* KPI strip */}
        {s && (
          <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-border border-b border-border">
            {[
              { label: "Trust Score", value: (s.trust_score * 100).toFixed(0) + "%", color: trustColor },
              { label: "Total Orders", value: s.total_orders.toLocaleString(), color: "#0f172a" },
              { label: "Delay Rate", value: s.delay_rate_pct.toFixed(1) + "%", color: s.delay_rate_pct > 20 ? "#ef4444" : s.delay_rate_pct > 10 ? "#f59e0b" : "#10b981" },
              { label: "Avg Delay", value: s.avg_delay_days.toFixed(1) + "d", color: s.avg_delay_days > 5 ? "#ef4444" : s.avg_delay_days > 2 ? "#f59e0b" : "#10b981" },
            ].map((stat) => (
              <div key={stat.label} className="px-5 py-3">
                <p className="text-[10px] font-semibold text-mutedForeground uppercase tracking-[0.08em]">{stat.label}</p>
                <p className="text-xl font-bold tabular-nums mt-0.5" style={{ color: stat.color }}>{stat.value}</p>
              </div>
            ))}
          </div>
        )}

        {/* Dual-axis chart */}
        <div className="px-4 py-5">
          {loading ? (
            <div className="h-[280px] flex items-center justify-center text-xs text-mutedForeground">Loading…</div>
          ) : !hasData ? (
            <div className="h-[280px] flex items-center justify-center text-xs text-mutedForeground">
              No order history for this supplier in the selected window
            </div>
          ) : (
            <>
              <div className="flex items-center gap-5 mb-3 flex-wrap">
                {[
                  { key: "On-Time %", color: "#10b981", note: "left axis" },
                  { key: "Delay (d)", color: "#f59e0b", note: "right axis" },
                  { key: "Deviations", color: "#ef4444", note: "right axis" },
                ].map((item) => (
                  <div key={item.key} className="flex items-center gap-1.5 text-[11px] text-mutedForeground">
                    <span className="h-2.5 w-2.5 rounded-sm" style={{ background: item.color }} />
                    {item.key}
                    <span className="text-[10px] opacity-50">({item.note})</span>
                  </div>
                ))}
              </div>
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={chartData} margin={{ top: 4, right: 40, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" />
                  <XAxis dataKey="week" tick={{ fontSize: 9, fill: "#94a3b8" }} interval="preserveStartEnd" />
                  {/* Left: On-Time % 0–100 */}
                  <YAxis yAxisId="pct" orientation="left" domain={[0, 100]} tick={{ fontSize: 9, fill: "#94a3b8" }} tickFormatter={(v) => `${v}%`} width={42} />
                  {/* Right: Delays & Deviations */}
                  <YAxis yAxisId="count" orientation="right" tick={{ fontSize: 9, fill: "#94a3b8" }} width={32} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area yAxisId="pct" type="monotone" dataKey="On-Time %" stroke="#10b981" fill="#10b981" fillOpacity={0.12} strokeWidth={2} dot={false} connectNulls />
                  <Bar yAxisId="count" dataKey="Deviations" fill="#ef4444" fillOpacity={0.55} radius={[2, 2, 0, 0]} maxBarSize={16} />
                  <Area yAxisId="count" type="monotone" dataKey="Delay (d)" stroke="#f59e0b" fill="none" strokeWidth={2} strokeDasharray="5 3" dot={false} connectNulls />
                </ComposedChart>
              </ResponsiveContainer>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
