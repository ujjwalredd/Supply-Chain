"use client";

import { useEffect, useState } from "react";
import { fetchSupplierRisk } from "@/lib/api";

type SupplierRiskItem = {
  supplier_id: string;
  name: string;
  region: string;
  trust_score: number;
  total_orders: number;
  delayed_orders: number;
  delay_rate_pct: number;
};

function trustColors(score: number) {
  if (score >= 85)
    return {
      bg: "rgba(124,106,247,0.1)",
      border: "rgba(124,106,247,0.25)",
      text: "#7c6af7",
      bar: "#7c6af7",
    };
  if (score >= 70)
    return {
      bg: "rgba(251,191,36,0.08)",
      border: "rgba(251,191,36,0.25)",
      text: "#fbbf24",
      bar: "#fbbf24",
    };
  return {
    bg: "rgba(248,113,113,0.08)",
    border: "rgba(248,113,113,0.25)",
    text: "#f87171",
    bar: "#f87171",
  };
}

export function SupplierHeatmap() {
  const [data, setData] = useState<SupplierRiskItem[]>([]);

  useEffect(() => {
    fetchSupplierRisk(12).then(setData).catch(() => setData([]));
  }, []);

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{ background: "#111117", border: "1px solid rgba(255,255,255,0.07)" }}
    >
      <div
        className="px-5 py-4 flex items-center justify-between"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}
      >
        <div>
          <p className="text-sm font-semibold text-foreground">Supplier Health</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">Trust score heatmap</p>
        </div>
        <div className="flex items-center gap-3">
          {[
            { c: "#7c6af7", l: "Trusted" },
            { c: "#fbbf24", l: "Watch" },
            { c: "#f87171", l: "Risk" },
          ].map((x) => (
            <div key={x.l} className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: x.c }} />
              <span className="text-[10px] text-mutedForeground">{x.l}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="p-4">
        {data.length === 0 && (
          <p className="text-xs text-mutedForeground px-1 py-6 text-center">
            No supplier data available.
          </p>
        )}
        <div className="grid grid-cols-2 gap-2">
          {data.map((s) => {
            const score = Math.round(s.trust_score * 100);
            const colors = trustColors(score);
            return (
              <div
                key={s.supplier_id}
                className="rounded-lg p-3"
                style={{ background: colors.bg, border: `1px solid ${colors.border}` }}
              >
                <div className="flex items-start justify-between gap-1">
                  <div className="min-w-0">
                    <p className="text-[11px] font-semibold text-foreground truncate font-mono">
                      {s.supplier_id}
                    </p>
                    <p className="text-[10px] text-mutedForeground truncate">{s.region}</p>
                  </div>
                  <span
                    className="text-sm font-bold tabular-nums shrink-0 ml-1"
                    style={{ color: colors.text }}
                  >
                    {score}
                  </span>
                </div>
                <div
                  className="mt-2 h-1 rounded-full overflow-hidden"
                  style={{ background: "rgba(255,255,255,0.06)" }}
                >
                  <div
                    className="h-1 rounded-full"
                    style={{ width: `${score}%`, background: colors.bar }}
                  />
                </div>
                <p className="text-[10px] text-mutedForeground mt-1.5">
                  {s.delayed_orders}/{s.total_orders} delayed
                </p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
