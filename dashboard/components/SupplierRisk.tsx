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
  max_product_dependency_pct?: number;
  concentration_risk?: string;
};

function trustColor(t: number) {
  return t >= 85 ? "#6366f1" : t >= 70 ? "#f59e0b" : "#ef4444";
}

function concentrationColor(risk?: string) {
  if (risk === "HIGH") return { bg: "rgba(239,68,68,0.08)", text: "#ef4444", border: "rgba(239,68,68,0.2)" };
  if (risk === "MEDIUM") return { bg: "rgba(245,158,11,0.08)", text: "#d97706", border: "rgba(245,158,11,0.2)" };
  return { bg: "rgba(16,185,129,0.08)", text: "#059669", border: "rgba(16,185,129,0.15)" };
}

export function SupplierRisk() {
  const [data, setData] = useState<SupplierRiskItem[]>([]);

  useEffect(() => {
    fetchSupplierRisk(10)
      .then(setData)
      .catch(() => setData([]));
  }, []);

  const chartData = data.map((s) => ({
    name: s.supplier_id.slice(0, 10),
    full: s.supplier_id,
    trust: Math.round(s.trust_score * 100),
    delayRate: Math.round(s.delay_rate_pct),
    concentration: s.concentration_risk ?? "LOW",
    depPct: Math.round(s.max_product_dependency_pct ?? 0),
  }));

  return (
    <div
      className="rounded-xl overflow-hidden bg-surface border border-border"
      style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}
    >
      <div className="px-5 py-4 border-b border-border">
        <p className="text-sm font-semibold text-foreground">Supplier Trust Scores</p>
        <p className="text-[11px] text-mutedForeground mt-0.5">Score 0–100 · hover for delay rate and dependency risk</p>
      </div>
      <div className="px-2 py-4">
        {chartData.length === 0 && (
          <p className="text-xs text-mutedForeground px-3 py-6">No supplier data available.</p>
        )}
        {chartData.length > 0 && (
          <>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={chartData} layout="vertical" margin={{ left: 4, right: 24, top: 4, bottom: 4 }}>
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                  axisLine={false}
                  tickLine={false}
                  tickCount={5}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={72}
                  tick={{ fontSize: 10, fill: "#64748b" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: "rgba(0,0,0,0.03)" }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.[0]) return null;
                    const d = payload[0].payload;
                    const cc = concentrationColor(d.concentration);
                    return (
                      <div
                        className="rounded-lg px-3 py-2.5 text-xs"
                        style={{ background: "#ffffff", border: "1px solid #e2e8f0", boxShadow: "0 4px 12px rgba(0,0,0,0.08)" }}
                      >
                        <p className="font-semibold text-foreground mb-2 font-mono">{d.full}</p>
                        <p className="text-mutedForeground">Trust: <span className="text-foreground font-medium">{d.trust}%</span></p>
                        <p className="text-mutedForeground">Delay rate: <span className="text-foreground font-medium">{d.delayRate}%</span></p>
                        <p className="text-mutedForeground mt-1">
                          Dependency:{" "}
                          <span
                            className="font-semibold px-1.5 py-0.5 rounded text-[10px]"
                            style={{ background: cc.bg, color: cc.text }}
                          >
                            {d.concentration} ({d.depPct}%)
                          </span>
                        </p>
                      </div>
                    );
                  }}
                />
                <Bar dataKey="trust" radius={[0, 4, 4, 0]} maxBarSize={12}>
                  {chartData.map((entry) => (
                    <Cell key={entry.name} fill={trustColor(entry.trust)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>

            <div className="flex items-center gap-5 px-3 mt-2">
              {[
                { c: "#6366f1", l: "≥85 trusted" },
                { c: "#f59e0b", l: "70–84 watch" },
                { c: "#ef4444", l: "<70 risk" },
              ].map((x) => (
                <div key={x.l} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full shrink-0" style={{ background: x.c }} />
                  <span className="text-[10px] text-mutedForeground">{x.l}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
