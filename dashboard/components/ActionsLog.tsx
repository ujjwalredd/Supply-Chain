"use client";

import { useEffect, useState } from "react";
import { fetchActions } from "@/lib/api";

type Action = {
  id: number;
  deviation_id: string;
  action_type: string;
  description: string;
  status: string;
  created_at: string;
  completed_at?: string;
};

const statusStyle: Record<string, { bg: string; color: string; border: string }> = {
  PENDING:   { bg: "rgba(245,158,11,0.08)",  color: "#d97706",  border: "rgba(245,158,11,0.2)" },
  COMPLETED: { bg: "rgba(16,185,129,0.08)",  color: "#059669",  border: "rgba(16,185,129,0.2)" },
  CANCELLED: { bg: "rgba(100,116,139,0.06)", color: "#64748b",  border: "rgba(100,116,139,0.12)" },
};

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const TYPE_LABEL: Record<string, string> = {
  REROUTE: "Reroute",
  EXPEDITE: "Expedite",
  SAFETY_STOCK: "Safety Stock",
  NOTIFY: "Notify",
  ESCALATE: "Escalate",
};

export function ActionsLog() {
  const [actions, setActions] = useState<Action[]>([]);

  useEffect(() => {
    fetchActions({ limit: 30 })
      .then(setActions)
      .catch(() => setActions([]));
    const id = setInterval(() => {
      fetchActions({ limit: 30 })
        .then(setActions)
        .catch(() => {});
    }, 15000);
    return () => clearInterval(id);
  }, []);

  const pending = actions.filter((a) => a.status === "PENDING").length;

  return (
    <div
      className="rounded-xl overflow-hidden bg-surface border border-border"
      style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}
    >
      <div className="px-5 py-4 flex items-center justify-between border-b border-border">
        <div>
          <p className="text-sm font-semibold text-foreground">Actions Log</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">AI-recommended autonomous actions</p>
        </div>
        {pending > 0 && (
          <span
            className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full"
            style={{ background: "rgba(245,158,11,0.08)", color: "#d97706", border: "1px solid rgba(245,158,11,0.2)" }}
          >
            {pending} pending
          </span>
        )}
      </div>
      <div className="overflow-y-auto max-h-[380px]">
        {actions.length === 0 && (
          <div className="px-5 py-10 text-center">
            <p className="text-xs text-mutedForeground">No actions yet. Click a deviation to trigger AI analysis.</p>
          </div>
        )}
        {actions.map((a, idx) => {
          const s = statusStyle[a.status] ?? statusStyle.CANCELLED;
          return (
            <div
              key={a.id}
              className="flex items-start gap-3 px-5 py-3.5 hover:bg-surfaceRaised transition-colors"
              style={{ borderBottom: idx < actions.length - 1 ? "1px solid #f1f5f9" : "none" }}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2 mb-0.5">
                  <p className="text-xs font-semibold text-foreground">
                    {TYPE_LABEL[a.action_type] ?? a.action_type}
                  </p>
                  <span
                    className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider shrink-0"
                    style={{ background: s.bg, color: s.color, border: `1px solid ${s.border}` }}
                  >
                    {a.status}
                  </span>
                </div>
                <p className="text-[11px] text-mutedForeground line-clamp-2 leading-relaxed">{a.description}</p>
                <p className="text-[10px] text-mutedForeground mt-1">{relativeTime(a.created_at)}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
