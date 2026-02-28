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

  const stats = [
    {
      label: "Pipeline Value",
      value: `$${((data.pipeline_value ?? 0) / 1_000_000).toFixed(1)}M`,
      color: "text-foreground",
    },
    {
      label: "On-Time",
      value: `${(data.on_time_pct ?? 0).toFixed(1)}%`,
      color: "text-foreground",
    },
    {
      label: "Delayed",
      value: `${data.delayed_count ?? 0}`,
      color: (data.delayed_count ?? 0) > 0 ? "text-warning" : "text-foreground",
    },
    {
      label: "Critical",
      value: `${data.critical_delays ?? 0}`,
      color: (data.critical_delays ?? 0) > 0 ? "text-destructive" : "text-foreground",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-border rounded-lg overflow-hidden">
      {stats.map((s) => (
        <div key={s.label} className="bg-card px-5 py-4">
          <p className="text-xs text-mutedForeground mb-1">{s.label}</p>
          <p className={`text-2xl font-semibold tabular-nums ${s.color}`}>{s.value}</p>
        </div>
      ))}
    </div>
  );
}
