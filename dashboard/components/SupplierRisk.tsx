"use client";

import { useEffect, useState } from "react";
import { fetchSupplierRisk } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

type SupplierRiskItem = {
  supplier_id: string;
  name: string;
  region: string;
  trust_score: number;
  total_orders: number;
  delayed_orders: number;
  delay_rate_pct: number;
};

export function SupplierRisk() {
  const [data, setData] = useState<SupplierRiskItem[]>([]);

  useEffect(() => {
    fetchSupplierRisk(15)
      .then(setData)
      .catch(() => setData([]));
  }, []);

  const chartData = data.map((s) => ({
    name: s.supplier_id,
    trust: Math.round(s.trust_score * 100),
    delayRate: Math.round(s.delay_rate_pct),
  }));

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <p className="text-sm font-medium text-foreground">Supplier Trust</p>
      </div>
      <div className="px-4 py-4">
        {chartData.length === 0 && (
          <p className="text-xs text-mutedForeground py-4">No supplier data.</p>
        )}
        {chartData.length > 0 && (
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 0, right: 16, top: 0, bottom: 0 }}>
              <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10, fill: "#71717a" }} axisLine={false} tickLine={false} />
              <YAxis type="category" dataKey="name" width={68} tick={{ fontSize: 11, fill: "#71717a" }} axisLine={false} tickLine={false} />
              <Tooltip
                cursor={{ fill: "#1a1a1e" }}
                content={({ active, payload }) =>
                  active && payload?.[0] ? (
                    <div className="bg-card border border-border rounded px-3 py-2 text-xs">
                      <p className="font-medium text-foreground mb-1">{payload[0].payload.name}</p>
                      <p className="text-mutedForeground">Trust: {payload[0].payload.trust}%</p>
                      <p className="text-mutedForeground">Delay rate: {payload[0].payload.delayRate}%</p>
                    </div>
                  ) : null
                }
              />
              <Bar dataKey="trust" radius={[0, 3, 3, 0]} maxBarSize={14}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.name}
                    fill={entry.trust >= 85 ? "#6366f1" : entry.trust >= 70 ? "#f59e0b" : "#ef4444"}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
