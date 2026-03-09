"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
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
    week: w.week.slice(5), // MM-DD
    "On-Time %": w.on_time_pct,
    "Avg Delay (d)": w.avg_delay_days,
    Deviations: w.deviation_count,
  }));

  const s = scorecard?.supplier;

  return (
    <div className="space-y-5">
      {/* Controls */}
      <div className="glass-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between flex-wrap gap-3">
          <div>
            <p className="text-sm font-semibold text-foreground">Supplier Scorecard</p>
            <p className="text-[11px] text-mutedForeground mt-0.5">
              Weekly performance trend — on-time rate, delays, and deviation frequency
            </p>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="text-[12px] font-medium text-foreground rounded-lg px-3 py-1.5 bg-surfaceRaised border border-border focus:outline-none focus:ring-1 focus:ring-accent"
            >
              {suppliers.map((s) => (
                <option key={s.supplier_id} value={s.supplier_id}>
                  {s.name} ({s.supplier_id})
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

        {/* Stats strip */}
        {s && (
          <div className="grid grid-cols-2 sm:grid-cols-4 divide-x divide-border border-b border-border">
            {[
              { label: "Trust Score", value: (s.trust_score * 100).toFixed(0) + "%", color: s.trust_score >= 0.85 ? "#10b981" : s.trust_score >= 0.70 ? "#f59e0b" : "#ef4444" },
              { label: "Total Orders", value: String(s.total_orders), color: "#0f172a" },
              { label: "Delay Rate", value: s.delay_rate_pct.toFixed(1) + "%", color: s.delay_rate_pct > 20 ? "#ef4444" : s.delay_rate_pct > 10 ? "#f59e0b" : "#10b981" },
              { label: "Avg Delay", value: s.avg_delay_days.toFixed(1) + "d", color: s.avg_delay_days > 5 ? "#ef4444" : "#0f172a" },
            ].map((stat) => (
              <div key={stat.label} className="px-5 py-3">
                <p className="text-[10px] font-semibold text-mutedForeground uppercase tracking-[0.08em]">{stat.label}</p>
                <p className="text-xl font-bold tabular-nums mt-0.5" style={{ color: stat.color }}>{stat.value}</p>
              </div>
            ))}
          </div>
        )}

        {/* Chart */}
        <div className="px-4 py-5">
          {loading ? (
            <div className="h-[260px] flex items-center justify-center text-xs text-mutedForeground">
              Loading…
            </div>
          ) : chartData.length === 0 ? (
            <div className="h-[260px] flex items-center justify-center text-xs text-mutedForeground">
              No order history for this supplier
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData} margin={{ top: 4, right: 12, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.04)" />
                <XAxis dataKey="week" tick={{ fontSize: 9, fill: "#94a3b8" }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 9, fill: "#94a3b8" }} />
                <Tooltip
                  contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 11 }}
                  labelStyle={{ color: "#0f172a", fontWeight: 600 }}
                />
                <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
                <Line type="monotone" dataKey="On-Time %" stroke="#10b981" strokeWidth={2} dot={false} connectNulls />
                <Line type="monotone" dataKey="Avg Delay (d)" stroke="#f59e0b" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                <Line type="monotone" dataKey="Deviations" stroke="#ef4444" strokeWidth={1.5} dot={false} strokeDasharray="2 4" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
