"use client";

import { useEffect, useState } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";

type KPIData = {
  pipeline_value?: number;
  on_time_pct?: number;
  delayed_count?: number;
  critical_delays?: number;
};

export function KPICards() {
  const [data, setData] = useState<KPIData>({});
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

  const onTimePct = data.on_time_pct ?? 0;
  const delayed = data.delayed_count ?? 0;
  const critical = data.critical_delays ?? 0;

  const stats = [
    {
      label: "Pipeline Value",
      value: `$${((data.pipeline_value ?? 0) / 1_000_000).toFixed(1)}M`,
      sub: "total order value",
      valueColor: "text-foreground",
      accentColor: "#7c6af7",
    },
    {
      label: "On-Time Rate",
      value: `${onTimePct.toFixed(1)}%`,
      sub: onTimePct >= 90 ? "on track" : onTimePct >= 75 ? "needs attention" : "at risk",
      valueColor: onTimePct >= 90 ? "text-success" : onTimePct >= 75 ? "text-warning" : "text-destructive",
      accentColor: onTimePct >= 90 ? "#34d399" : onTimePct >= 75 ? "#fbbf24" : "#f87171",
    },
    {
      label: "Delayed Orders",
      value: String(delayed),
      sub: delayed > 0 ? "require action" : "all on schedule",
      valueColor: delayed > 0 ? "text-warning" : "text-foreground",
      accentColor: delayed > 0 ? "#fbbf24" : "#34d399",
    },
    {
      label: "Critical Alerts",
      value: String(critical),
      sub: critical > 0 ? "escalation required" : "no critical alerts",
      valueColor: critical > 0 ? "text-destructive" : "text-foreground",
      accentColor: critical > 0 ? "#f87171" : "#34d399",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {stats.map((s) => (
        <div
          key={s.label}
          className="relative bg-card rounded-xl overflow-hidden"
          style={{ border: "1px solid rgba(255,255,255,0.07)" }}
        >
          {/* Left accent bar */}
          <div
            className="absolute left-0 top-0 bottom-0 w-0.5"
            style={{ background: s.accentColor, opacity: 0.8 }}
          />
          <div className="px-5 py-5">
            <p className="text-[11px] font-medium text-mutedForeground uppercase tracking-[0.08em] mb-3">
              {s.label}
            </p>
            <p className={`text-[28px] font-bold tabular-nums leading-none ${s.valueColor}`}>
              {s.value}
            </p>
            <p className="text-[11px] text-mutedForeground mt-2">{s.sub}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
