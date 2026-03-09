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
  max_product_dependency_pct?: number;
  concentration_risk?: string;
};

function trustColors(score: number) {
  if (score >= 85)
    return { bg: "rgba(99,102,241,0.06)", border: "rgba(99,102,241,0.15)", text: "#6366f1", bar: "#6366f1" };
  if (score >= 70)
    return { bg: "rgba(245,158,11,0.06)", border: "rgba(245,158,11,0.18)", text: "#d97706", bar: "#f59e0b" };
  return { bg: "rgba(239,68,68,0.06)", border: "rgba(239,68,68,0.18)", text: "#ef4444", bar: "#ef4444" };
}

function concentrationBadge(risk?: string) {
  if (risk === "HIGH") return { label: "HIGH dep", bg: "rgba(239,68,68,0.08)", color: "#ef4444" };
  if (risk === "MEDIUM") return { label: "MED dep", bg: "rgba(245,158,11,0.08)", color: "#d97706" };
  return { label: "LOW dep", bg: "rgba(16,185,129,0.08)", color: "#059669" };
}

export function SupplierHeatmap() {
  const [data, setData] = useState<SupplierRiskItem[]>([]);

  useEffect(() => {
    fetchSupplierRisk(12).then(setData).catch(() => setData([]));
  }, []);

  return (
    <div
      className="rounded-xl overflow-hidden bg-surface border border-border"
      style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}
    >
      <div className="px-5 py-4 flex items-center justify-between border-b border-border">
        <div>
          <p className="text-sm font-semibold text-foreground">Supplier Health Grid</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">Trust score, delay rate and dependency concentration</p>
        </div>
        <div className="flex items-center gap-3">
          {[
            { c: "#6366f1", l: "Trusted" },
            { c: "#f59e0b", l: "Watch" },
            { c: "#ef4444", l: "Risk" },
          ].map((x) => (
            <div key={x.l} className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full shrink-0" style={{ background: x.c }} />
              <span className="text-[10px] text-mutedForeground">{x.l}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="p-4">
        {data.length === 0 && (
          <p className="text-xs text-mutedForeground px-1 py-6 text-center">No supplier data available.</p>
        )}
        <div className="grid grid-cols-2 gap-2">
          {data.map((s) => {
            const score = Math.round(s.trust_score * 100);
            const colors = trustColors(score);
            const badge = concentrationBadge(s.concentration_risk);
            const depPct = Math.round(s.max_product_dependency_pct ?? 0);
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
                  <span className="text-base font-bold tabular-nums shrink-0 ml-1" style={{ color: colors.text }}>
                    {score}
                  </span>
                </div>

                {/* Trust bar */}
                <div className="mt-2 h-1.5 rounded-full overflow-hidden bg-border">
                  <div
                    className="h-1.5 rounded-full transition-all"
                    style={{ width: `${score}%`, background: colors.bar }}
                  />
                </div>

                <div className="flex items-center justify-between mt-2">
                  <p className="text-[10px] text-mutedForeground">
                    {s.delayed_orders}/{s.total_orders} delayed
                  </p>
                  <span
                    className="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide"
                    style={{ background: badge.bg, color: badge.color }}
                    title={`Product dependency: ${depPct}%`}
                  >
                    {badge.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
