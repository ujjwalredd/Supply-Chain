"use client";

import { useEffect, useState } from "react";
import { fetchActionsAudit, resolveAction, fetchActionSuccessRates } from "@/lib/api";
import { CheckCircle, XCircle } from "lucide-react";

type AuditRow = {
  action_id: number;
  action_type: string;
  status: string;
  confidence: number | null;
  reasoning: string | null;
  created_at: string;
  executed_at: string | null;
  resolved?: boolean;
  outcome_note?: string | null;
  resolved_at?: string | null;
  deviation_id: string | null;
  deviation_type: string | null;
  severity: string | null;
  order_id: string | null;
  supplier_id: string | null;
  order_value: number | null;
  product: string | null;
};

type SuccessRate = {
  action_type: string;
  total: number;
  resolved_count: number;
  success_count: number;
  success_rate_pct: number | null;
  avg_confidence: number;
};

const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  EXECUTED: { bg: "rgba(16,185,129,0.08)", color: "#10b981" },
  PENDING:  { bg: "rgba(245,158,11,0.08)", color: "#d97706" },
  REJECTED: { bg: "rgba(239,68,68,0.08)", color: "#ef4444" },
  CANCELLED: { bg: "rgba(0,0,0,0.05)", color: "#94a3b8" },
  FAILED:   { bg: "rgba(239,68,68,0.08)", color: "#ef4444" },
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

function ResolveDialog({
  actionId,
  onDone,
  onCancel,
}: {
  actionId: number;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [note, setNote] = useState("");
  const [success, setSuccess] = useState(true);
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!note.trim()) return;
    setSaving(true);
    try {
      await resolveAction(actionId, note.trim(), success);
      onDone();
    } catch {
      setSaving(false);
    }
  };

  return (
    <div className="px-5 pb-4">
      <div className="rounded-lg p-3 space-y-2.5" style={{ background: "rgba(0,112,243,0.03)", border: "1px solid rgba(0,112,243,0.12)" }}>
        <p className="text-[11px] font-semibold text-foreground">Record outcome</p>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="What happened? Did the action resolve the issue?"
          rows={2}
          className="w-full text-[12px] text-foreground rounded-lg px-3 py-2 bg-white border border-border focus:outline-none focus:ring-1 focus:ring-accent placeholder:text-mutedForeground resize-none"
        />
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" checked={success} onChange={(e) => setSuccess(e.target.checked)} className="accent-accent" />
            <span className="text-[11px] text-foreground">Successful outcome</span>
          </label>
          <div className="ml-auto flex gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="px-3 py-1 rounded-lg text-[11px] border border-border hover:bg-surfaceRaised transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={submit}
              disabled={!note.trim() || saving}
              className="px-3 py-1 rounded-lg text-[11px] text-white font-medium disabled:opacity-40 transition-colors"
              style={{ background: "#0070F3" }}
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AuditTrail() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [rates, setRates] = useState<SuccessRate[]>([]);
  const [limit, setLimit] = useState<(typeof LIMIT_OPTIONS)[number]>(50);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [resolving, setResolving] = useState<number | null>(null);

  const load = () => {
    setLoading(true);
    Promise.all([
      fetchActionsAudit(limit),
      fetchActionSuccessRates().catch(() => ({ success_rates: [] })),
    ])
      .then(([auditData, ratesData]) => {
        setRows(Array.isArray(auditData) ? auditData : auditData.actions ?? []);
        setRates(ratesData.success_rates ?? []);
      })
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [limit]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-4">
      {/* Success rates strip */}
      {rates.length > 0 && (
        <div className="glass-card overflow-hidden">
          <div className="px-5 py-3 border-b border-border">
            <p className="text-[11px] font-semibold text-foreground">Feedback Loop — Action Success Rates</p>
          </div>
          <div className="px-5 py-3 flex flex-wrap gap-3">
            {rates.map((r) => (
              <div key={r.action_type} className="flex items-center gap-2">
                <span className="text-[11px] text-mutedForeground">{r.action_type.replace(/_/g, " ")}</span>
                <span
                  className="text-[11px] font-bold tabular-nums"
                  style={{
                    color: r.success_rate_pct === null ? "#94a3b8"
                      : r.success_rate_pct >= 80 ? "#10b981"
                      : r.success_rate_pct >= 50 ? "#d97706"
                      : "#ef4444",
                  }}
                >
                  {r.success_rate_pct !== null ? `${r.success_rate_pct}%` : "—"}
                </span>
                <span className="text-[10px] text-mutedForeground">({r.resolved_count}/{r.total})</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="glass-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-foreground">Audit Trail</p>
            <p className="text-[11px] text-mutedForeground mt-0.5">
              Every AI recommendation logged — click to expand reasoning and record outcomes
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
              const isResolvable = row.status === "EXECUTED" && !row.resolved;
              return (
                <div key={row.action_id}>
                  <button
                    type="button"
                    onClick={() => setExpanded(isOpen ? null : row.action_id)}
                    className="w-full px-5 py-3.5 flex items-center gap-4 text-left hover:bg-surfaceRaised transition-colors"
                  >
                    {/* Status */}
                    <span
                      className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold shrink-0"
                      style={{ background: st.bg, color: st.color }}
                    >
                      {row.status}
                    </span>

                    {/* Resolved badge */}
                    {row.resolved && (
                      <CheckCircle className="h-3.5 w-3.5 text-success shrink-0" />
                    )}

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[12px] font-medium text-foreground">
                          {row.action_type.replace(/_/g, " ")}
                        </span>
                        {row.severity && (
                          <span className="text-[10px] font-semibold" style={{ color: SEV_COLOR[row.severity] ?? "#6b7280" }}>
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
                        {[row.order_id && `Order ${row.order_id}`, row.supplier_id, row.product, row.order_value && `$${row.order_value.toLocaleString()}`]
                          .filter(Boolean).join(" · ")}
                      </p>
                    </div>

                    {/* Confidence */}
                    {row.confidence !== null && (
                      <span
                        className="text-[11px] font-semibold tabular-nums shrink-0"
                        style={{ color: row.confidence >= 0.85 ? "#10b981" : row.confidence >= 0.6 ? "#d97706" : "#ef4444" }}
                      >
                        {(row.confidence * 100).toFixed(0)}%
                      </span>
                    )}

                    <time className="text-[10px] text-mutedForeground shrink-0 hidden sm:block whitespace-nowrap">
                      {fmt(row.created_at)}
                    </time>
                  </button>

                  {/* Expanded */}
                  {isOpen && (
                    <div className="space-y-2">
                      {row.reasoning && (
                        <div className="px-5">
                          <div
                            className="rounded-lg p-3 text-[12px] leading-relaxed text-foreground"
                            style={{ background: "rgba(0,0,0,0.02)", border: "1px solid #e2e8f0" }}
                          >
                            <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground mb-1.5">AI Reasoning</p>
                            <p className="whitespace-pre-wrap">{row.reasoning}</p>
                            {row.executed_at && (
                              <p className="mt-2 text-[10px] text-mutedForeground">Executed {fmt(row.executed_at)}</p>
                            )}
                          </div>
                        </div>
                      )}
                      {/* Outcome note if already resolved */}
                      {row.resolved && row.outcome_note && (
                        <div className="px-5 pb-3">
                          <div className="rounded-lg p-3" style={{ background: "rgba(16,185,129,0.04)", border: "1px solid rgba(16,185,129,0.15)" }}>
                            <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-success mb-1">Outcome</p>
                            <p className="text-[12px] text-foreground">{row.outcome_note}</p>
                            {row.resolved_at && (
                              <p className="mt-1 text-[10px] text-mutedForeground">Resolved {fmt(row.resolved_at)}</p>
                            )}
                          </div>
                        </div>
                      )}
                      {/* Resolve button */}
                      {isResolvable && resolving !== row.action_id && (
                        <div className="px-5 pb-4 flex gap-2">
                          <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); setResolving(row.action_id); }}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors"
                            style={{ background: "rgba(16,185,129,0.08)", color: "#10b981", border: "1px solid rgba(16,185,129,0.2)" }}
                          >
                            <CheckCircle className="h-3 w-3" />
                            Record Outcome
                          </button>
                          <button
                            type="button"
                            onClick={async (e) => {
                              e.stopPropagation();
                              await resolveAction(row.action_id, "Marked as failed", false);
                              load();
                            }}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors"
                            style={{ background: "rgba(239,68,68,0.06)", color: "#ef4444", border: "1px solid rgba(239,68,68,0.15)" }}
                          >
                            <XCircle className="h-3 w-3" />
                            Mark Failed
                          </button>
                        </div>
                      )}
                      {resolving === row.action_id && (
                        <ResolveDialog
                          actionId={row.action_id}
                          onDone={() => { setResolving(null); load(); }}
                          onCancel={() => setResolving(null)}
                        />
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
