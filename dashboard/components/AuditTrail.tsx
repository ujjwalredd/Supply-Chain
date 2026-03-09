"use client";

import { useEffect, useState } from "react";
import { fetchActionsAudit } from "@/lib/api";

type AuditRow = {
  action_id: number;
  action_type: string;
  status: string;
  confidence: number | null;
  reasoning: string | null;
  created_at: string;
  executed_at: string | null;
  deviation_id: string | null;
  deviation_type: string | null;
  severity: string | null;
  order_id: string | null;
  supplier_id: string | null;
  order_value: number | null;
  product: string | null;
};

const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  EXECUTED: { bg: "rgba(16,185,129,0.08)", color: "#10b981" },
  PENDING: { bg: "rgba(245,158,11,0.08)", color: "#d97706" },
  REJECTED: { bg: "rgba(239,68,68,0.08)", color: "#ef4444" },
  CANCELLED: { bg: "rgba(0,0,0,0.05)", color: "#94a3b8" },
};

const SEV_COLOR: Record<string, string> = {
  CRITICAL: "#ef4444",
  HIGH: "#d97706",
  MEDIUM: "#0070F3",
  LOW: "#6b7280",
};

function fmt(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

const LIMIT_OPTIONS = [20, 50, 100] as const;

export function AuditTrail() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [limit, setLimit] = useState<(typeof LIMIT_OPTIONS)[number]>(50);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchActionsAudit(limit)
      .then((data) => setRows(Array.isArray(data) ? data : data.actions ?? []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [limit]);

  return (
    <div className="glass-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">Audit Trail</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">
            Every AI recommendation and executed action with full context
          </p>
        </div>
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value) as typeof limit)}
          className="text-[12px] font-medium text-foreground rounded-lg px-3 py-1.5 bg-surfaceRaised border border-border focus:outline-none focus:ring-1 focus:ring-accent"
        >
          {LIMIT_OPTIONS.map((n) => (
            <option key={n} value={n}>Last {n}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="px-5 py-10 text-center text-xs text-mutedForeground">Loading audit records…</div>
      ) : rows.length === 0 ? (
        <div className="px-5 py-10 text-center text-xs text-mutedForeground">No audit records found</div>
      ) : (
        <div className="divide-y divide-border">
          {rows.map((row) => {
            const st = STATUS_STYLE[row.status] ?? STATUS_STYLE.CANCELLED;
            const isOpen = expanded === row.action_id;
            return (
              <div key={row.action_id}>
                <button
                  type="button"
                  onClick={() => setExpanded(isOpen ? null : row.action_id)}
                  className="w-full px-5 py-3.5 flex items-center gap-4 text-left hover:bg-surfaceRaised transition-colors"
                >
                  {/* Status pill */}
                  <span
                    className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold shrink-0"
                    style={{ background: st.bg, color: st.color }}
                  >
                    {row.status}
                  </span>

                  {/* Action + context */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[12px] font-medium text-foreground">
                        {row.action_type.replace(/_/g, " ")}
                      </span>
                      {row.severity && (
                        <span
                          className="text-[10px] font-semibold"
                          style={{ color: SEV_COLOR[row.severity] ?? "#6b7280" }}
                        >
                          {row.severity}
                        </span>
                      )}
                      {row.deviation_type && (
                        <span className="text-[10px] text-mutedForeground">
                          {row.deviation_type.replace(/_/g, " ")}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-mutedForeground mt-0.5 truncate">
                      {row.order_id ? `Order ${row.order_id}` : ""}
                      {row.supplier_id ? ` · ${row.supplier_id}` : ""}
                      {row.product ? ` · ${row.product}` : ""}
                      {row.order_value ? ` · $${row.order_value.toLocaleString()}` : ""}
                    </p>
                  </div>

                  {/* Confidence */}
                  {row.confidence !== null && (
                    <span className="text-[11px] font-semibold tabular-nums shrink-0" style={{ color: row.confidence >= 0.85 ? "#10b981" : row.confidence >= 0.6 ? "#d97706" : "#ef4444" }}>
                      {(row.confidence * 100).toFixed(0)}%
                    </span>
                  )}

                  {/* Timestamp */}
                  <time className="text-[10px] text-mutedForeground shrink-0 hidden sm:block whitespace-nowrap">
                    {fmt(row.created_at)}
                  </time>
                </button>

                {/* Expanded reasoning */}
                {isOpen && row.reasoning && (
                  <div className="px-5 pb-4">
                    <div
                      className="rounded-lg p-3 text-[12px] leading-relaxed text-foreground"
                      style={{ background: "rgba(0,0,0,0.02)", border: "1px solid #e2e8f0" }}
                    >
                      <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground mb-1.5">
                        AI Reasoning
                      </p>
                      <p className="whitespace-pre-wrap">{row.reasoning}</p>
                      {row.executed_at && (
                        <p className="mt-2 text-[10px] text-mutedForeground">
                          Executed at {fmt(row.executed_at)}
                        </p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
