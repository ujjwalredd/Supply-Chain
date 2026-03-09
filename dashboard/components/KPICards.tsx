"use client";

import { useEffect, useState } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { fetchActionsStats } from "@/lib/api";

type KPIData = {
  pipeline_value?: number;
  on_time_pct?: number;
  delayed_count?: number;
  critical_delays?: number;
};

export function KPICards() {
  const [data, setData] = useState<KPIData>({});
  const [mttr, setMttr] = useState<number | null>(null);
  const { lastMessage } = useWebSocket((msg) => {
    if (msg.type === "kpi" && msg.data) setData(msg.data as KPIData);
  });

  useEffect(() => {
    async function fetchKPIs() {
      try {
        const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const ordersRes = await fetch(`${base}/orders?limit=500`);
        const orders = await ordersRes.json();
        const total = orders.length;
        const delayed = orders.filter((o: { delay_days?: number }) => (o.delay_days ?? 0) > 0).length;
        const critical = orders.filter((o: { delay_days?: number }) => (o.delay_days ?? 0) > 7).length;
        const value = orders.reduce((s: number, o: { order_value?: number }) => s + (o.order_value ?? 0), 0);
        setData({
          pipeline_value: value,
          on_time_pct: total > 0 ? ((total - delayed) / total) * 100 : 0,
          delayed_count: delayed,
          critical_delays: critical,
        });
      } catch {
        setData({ pipeline_value: 0, on_time_pct: 0, delayed_count: 0, critical_delays: 0 });
      }
    }
    fetchKPIs();
    const id = setInterval(fetchKPIs, 30000);
    return () => clearInterval(id);
  }, [lastMessage]);

  useEffect(() => {
    fetchActionsStats()
      .then((s) => setMttr(s.mttr_minutes ?? null))
      .catch(() => setMttr(null));
  }, []);

  const onTimePct = data.on_time_pct ?? 0;
  const delayed = data.delayed_count ?? 0;
  const critical = data.critical_delays ?? 0;

  const stats = [
    {
      label: "Pipeline Value",
      value: `$${((data.pipeline_value ?? 0) / 1_000_000).toFixed(1)}M`,
      sub: "total order value",
      valueColor: "#0f172a",
      accentColor: "#0070F3",
      iconBg: "rgba(0,112,243,0.08)",
    },
    {
      label: "On-Time Rate",
      value: `${onTimePct.toFixed(1)}%`,
      sub: onTimePct >= 90 ? "on track" : onTimePct >= 75 ? "needs attention" : "at risk",
      valueColor: onTimePct >= 90 ? "#10b981" : onTimePct >= 75 ? "#d97706" : "#ef4444",
      accentColor: onTimePct >= 90 ? "#10b981" : onTimePct >= 75 ? "#f59e0b" : "#ef4444",
      iconBg: onTimePct >= 90 ? "rgba(16,185,129,0.08)" : onTimePct >= 75 ? "rgba(245,158,11,0.08)" : "rgba(239,68,68,0.08)",
    },
    {
      label: "Delayed Orders",
      value: String(delayed),
      sub: delayed > 0 ? "require attention" : "all on schedule",
      valueColor: delayed > 0 ? "#d97706" : "#10b981",
      accentColor: delayed > 0 ? "#f59e0b" : "#10b981",
      iconBg: delayed > 0 ? "rgba(245,158,11,0.08)" : "rgba(16,185,129,0.08)",
    },
    {
      label: "Critical Alerts",
      value: String(critical),
      sub: critical > 0 ? "escalation required" : "no critical alerts",
      valueColor: critical > 0 ? "#ef4444" : "#10b981",
      accentColor: critical > 0 ? "#ef4444" : "#10b981",
      iconBg: critical > 0 ? "rgba(239,68,68,0.08)" : "rgba(16,185,129,0.08)",
    },
    {
      label: "Avg Resolution",
      value:
        mttr === null ? "N/A"
        : mttr < 1 ? "<1m"
        : mttr < 60 ? `${Math.round(mttr)}m`
        : mttr < 1440 ? `${(mttr / 60).toFixed(1)}h`
        : `${(mttr / 1440).toFixed(1)}d`,
      sub: "mean time to resolve",
      valueColor: mttr === null ? "#94a3b8" : mttr <= 30 ? "#10b981" : mttr <= 240 ? "#d97706" : "#ef4444",
      accentColor: mttr === null ? "#94a3b8" : mttr <= 30 ? "#10b981" : mttr <= 240 ? "#f59e0b" : "#ef4444",
      iconBg: "rgba(0,112,243,0.06)",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {stats.map((s) => (
        <div
          key={s.label}
          className="relative bg-surface rounded-xl overflow-hidden border border-border"
          style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}
        >
          <div
            className="absolute left-0 top-0 bottom-0 w-0.5"
            style={{ background: s.accentColor }}
          />
          <div className="px-5 py-5">
            <p className="text-[10px] font-semibold text-mutedForeground uppercase tracking-[0.08em] mb-3">
              {s.label}
            </p>
            <p className="text-[26px] font-bold tabular-nums leading-none" style={{ color: s.valueColor }}>
              {s.value}
            </p>
            <p className="text-[11px] text-mutedForeground mt-2">{s.sub}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
