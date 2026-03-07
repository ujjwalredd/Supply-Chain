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

const statusStyle: Record<string, { bg: string; color: string }> = {
  PENDING:   { bg: "rgba(251,191,36,0.1)",  color: "#fbbf24" },
  COMPLETED: { bg: "rgba(52,211,153,0.1)",  color: "#34d399" },
  CANCELLED: { bg: "rgba(255,255,255,0.05)", color: "#52526a" },
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
    <div className="rounded-xl overflow-hidden" style={{ background: "#111117", border: "1px solid rgba(255,255,255,0.07)" }}>
      <div className="px-5 py-4 flex items-center justify-between" style={{ borderBottom: "1px solid rgba(255,255,255,0.07)" }}>
        <div>
          <p className="text-sm font-semibold text-foreground">Actions Log</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">AI-recommended actions</p>
        </div>
        {pending > 0 && (
          <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md" style={{ background: "rgba(251,191,36,0.1)", color: "#fbbf24" }}>
            {pending} pending
          </span>
        )}
      </div>
      <div className="overflow-y-auto max-h-[320px]">
        {actions.length === 0 && (
          <div className="px-5 py-10 text-center">
            <p className="text-xs text-mutedForeground">No actions yet. Click a deviation and execute a recommendation.</p>
          </div>
        )}
        {actions.map((a, idx) => {
          const s = statusStyle[a.status] ?? statusStyle.CANCELLED;
          return (
            <div
              key={a.id}
              className="flex items-start gap-4 px-5 py-3.5 transition-colors"
              style={{ borderBottom: idx < actions.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none" }}
              onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.02)"; }}
              onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = "transparent"; }}
            >
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-foreground truncate capitalize">
                  {a.action_type.replace(/_/g, " ").toLowerCase()}
                </p>
                <p className="text-[11px] text-mutedForeground mt-0.5 line-clamp-2">{a.description}</p>
              </div>
              <div className="shrink-0 text-right">
                <span
                  className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide"
                  style={{ background: s.bg, color: s.color }}
                >
                  {a.status}
                </span>
                <p className="text-[10px] text-mutedForeground mt-1">{relativeTime(a.created_at)}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
