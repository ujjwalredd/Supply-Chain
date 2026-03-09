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
  return t >= 85 ? "#7c6af7" : t >= 70 ? "#fbbf24" : "#f87171";
}

function concentrationColor(risk?: string) {
  if (risk === "HIGH") return { bg: "rgba(248,113,113,0.12)", text: "#f87171", border: "rgba(248,113,113,0.25)" };
  if (risk === "MEDIUM") return { bg: "rgba(251,191,36,0.1)", text: "#fbbf24", border: "rgba(251,191,36,0.25)" };
  return { bg: "rgba(52,211,153,0.08)", text: "#34d399", border: "rgba(52,211,153,0.2)" };
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
    <div className="rounded-xl overflow-hidden" style={{ background: "#111117", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="px-5 py-4" style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}>
        <p className="text-sm font-semibold text-foreground">Supplier Trust Score</p>
        <p className="text-[11px] text-mutedForeground mt-0.5">Trust score (0–100) with delay rate and dependency risk</p>
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
                  tick={{ fontSize: 10, fill: "#52526a" }}
                  axisLine={false}
                  tickLine={false}
                  tickCount={5}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={72}
                  tick={{ fontSize: 10, fill: "#52526a" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.025)" }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.[0]) return null;
                    const d = payload[0].payload;
                    const cc = concentrationColor(d.concentration);
                    return (
                      <div className="rounded-lg px-3 py-2.5 text-xs shadow-md" style={{ background: "#16161e", border: "1px solid rgba(255,255,255,0.1)" }}>
                        <p className="font-semibold text-foreground mb-2 font-mono">{d.full}</p>
                        <p className="text-mutedForeground">Trust: <span className="text-foreground font-medium">{d.trust}%</span></p>
                        <p className="text-mutedForeground">Delay rate: <span className="text-foreground font-medium">{d.delayRate}%</span></p>
                        <p className="text-mutedForeground mt-1">
                          Dependency:{" "}
                          <span className="font-semibold px-1.5 py-0.5 rounded text-[10px]" style={{ background: cc.bg, color: cc.text }}>
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

            {/* Legend */}
            <div className="flex items-center justify-between px-3 mt-2">
              <div className="flex items-center gap-4">
                {[{ c: "#7c6af7", l: "≥85 trusted" }, { c: "#fbbf24", l: "70–84 watch" }, { c: "#f87171", l: "<70 risk" }].map((x) => (
                  <div key={x.l} className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full shrink-0" style={{ background: x.c }} />
                    <span className="text-[10px] text-mutedForeground">{x.l}</span>
                  </div>
                ))}
              </div>
              <span className="text-[10px] text-mutedForeground">Hover for details</span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
