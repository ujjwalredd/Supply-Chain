"use client";

import { useEffect, useState } from "react";
import { fetchSupplierBenchmarks } from "@/lib/api";

type Benchmark = {
  rank: number;
  supplier_id: string;
  name: string;
  region: string;
  trust_score: number;
  total_orders: number;
  delayed_count: number;
  on_time_rate_pct: number;
  avg_delay_days: number;
  composite_score: number;
  products: string[];
};

function Medal({ rank }: { rank: number }) {
  if (rank === 1) return <span className="text-[13px]">🥇</span>;
  if (rank === 2) return <span className="text-[13px]">🥈</span>;
  if (rank === 3) return <span className="text-[13px]">🥉</span>;
  return <span className="text-[11px] tabular-nums text-mutedForeground w-5 text-center">#{rank}</span>;
}

function ScoreBar({ score, max }: { score: number; max: number }) {
  const pct = max > 0 ? (score / max) * 100 : 0;
  const color = score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : "#ef4444";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-border overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="text-[11px] tabular-nums font-semibold shrink-0 w-8 text-right" style={{ color }}>
        {score.toFixed(0)}
      </span>
    </div>
  );
}

export function SupplierBenchmark() {
  const [data, setData] = useState<Benchmark[]>([]);
  const [loading, setLoading] = useState(true);
  const [product, setProduct] = useState("");
  const [inputProduct, setInputProduct] = useState("");

  useEffect(() => {
    setLoading(true);
    fetchSupplierBenchmarks(product || undefined)
      .then((d) => setData(d.benchmarks ?? []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [product]);

  const maxScore = Math.max(...data.map((d) => d.composite_score), 1);

  return (
    <div className="glass-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="text-sm font-semibold text-foreground">Supplier Benchmarks</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">
            Side-by-side performance ranking — on-time rate, delay, and composite score
          </p>
        </div>
        <form
          className="flex gap-2"
          onSubmit={(e) => { e.preventDefault(); setProduct(inputProduct.trim()); }}
        >
          <input
            type="text"
            value={inputProduct}
            onChange={(e) => setInputProduct(e.target.value)}
            placeholder="Filter by product…"
            className="text-[12px] text-foreground rounded-lg px-3 py-1.5 bg-surfaceRaised border border-border focus:outline-none focus:ring-1 focus:ring-accent placeholder:text-mutedForeground w-40"
          />
          <button
            type="submit"
            className="px-3 py-1.5 rounded-lg text-[11px] font-medium text-white transition-colors"
            style={{ background: "#0070F3" }}
          >
            Filter
          </button>
          {product && (
            <button
              type="button"
              onClick={() => { setProduct(""); setInputProduct(""); }}
              className="px-3 py-1.5 rounded-lg text-[11px] font-medium border border-border hover:bg-surfaceRaised transition-colors"
            >
              Clear
            </button>
          )}
        </form>
      </div>

      {loading ? (
        <div className="px-5 py-10 text-center text-xs text-mutedForeground">Loading benchmarks…</div>
      ) : data.length === 0 ? (
        <div className="px-5 py-10 text-center text-xs text-mutedForeground">No suppliers found{product ? ` for "${product}"` : ""}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-surfaceRaised border-b border-border">
              <tr>
                {["Rank", "Supplier", "Region", "Orders", "On-Time %", "Avg Delay", "Composite Score"].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((r, i) => (
                <tr
                  key={r.supplier_id}
                  className="hover:bg-surfaceRaised transition-colors"
                  style={{ borderTop: i > 0 ? "1px solid #f1f5f9" : undefined }}
                >
                  <td className="px-4 py-3">
                    <Medal rank={r.rank} />
                  </td>
                  <td className="px-4 py-3">
                    <p className="text-xs font-medium text-foreground">{r.name}</p>
                    {r.products.length > 0 && (
                      <p className="text-[10px] text-mutedForeground mt-0.5 truncate max-w-[160px]">
                        {r.products.slice(0, 3).join(", ")}
                        {r.products.length > 3 && ` +${r.products.length - 3}`}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-3 text-[11px] text-mutedForeground">{r.region}</td>
                  <td className="px-4 py-3 text-xs tabular-nums text-foreground">{r.total_orders}</td>
                  <td className="px-4 py-3">
                    <span
                      className="text-xs font-semibold tabular-nums"
                      style={{ color: r.on_time_rate_pct >= 90 ? "#10b981" : r.on_time_rate_pct >= 75 ? "#d97706" : "#ef4444" }}
                    >
                      {r.on_time_rate_pct.toFixed(1)}%
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="text-xs tabular-nums"
                      style={{ color: r.avg_delay_days > 5 ? "#ef4444" : r.avg_delay_days > 2 ? "#d97706" : "#94a3b8" }}
                    >
                      {r.avg_delay_days.toFixed(1)}d
                    </span>
                  </td>
                  <td className="px-4 py-3 min-w-[120px]">
                    <ScoreBar score={r.composite_score} max={maxScore} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
