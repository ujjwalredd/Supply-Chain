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

const statusColor: Record<string, string> = {
  PENDING: "text-warning",
  COMPLETED: "text-success",
  CANCELLED: "text-mutedForeground",
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

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <p className="text-sm font-medium text-foreground">Actions Log</p>
        <p className="text-xs text-mutedForeground">{actions.filter((a) => a.status === "PENDING").length} pending</p>
      </div>
      <div className="divide-y divide-border max-h-[320px] overflow-y-auto">
        {actions.length === 0 && (
          <p className="text-xs text-mutedForeground px-4 py-6">No actions yet. Execute a recommendation to see it here.</p>
        )}
        {actions.map((a) => (
          <div key={a.id} className="flex items-start justify-between px-4 py-3 gap-4">
            <div className="min-w-0">
              <p className="text-sm font-medium text-foreground truncate">{a.action_type.replace(/_/g, " ")}</p>
              <p className="text-xs text-mutedForeground mt-0.5 line-clamp-2">{a.description}</p>
            </div>
            <div className="shrink-0 text-right">
              <p className={`text-xs font-medium ${statusColor[a.status] ?? "text-mutedForeground"}`}>{a.status}</p>
              <p className="text-xs text-mutedForeground mt-0.5">{relativeTime(a.created_at)}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
