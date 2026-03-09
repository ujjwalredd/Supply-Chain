"use client";

import { useEffect, useState } from "react";
import { fetchDeviationClusters } from "@/lib/api";

type Cluster = {
  type: string;
  supplier_id: string;
  count: number;
  critical_count: number;
  last_seen: string;
};

const DAY_OPTIONS = [7, 14, 30, 60, 90] as const;

function typeLabel(t: string) {
  return t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function daysAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const d = Math.floor(diff / 86_400_000);
  return d === 0 ? "today" : d === 1 ? "1d ago" : `${d}d ago`;
}

export function DeviationClusters() {
  const [days, setDays] = useState<(typeof DAY_OPTIONS)[number]>(30);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchDeviationClusters(days)
      .then((data) => setClusters(data.clusters ?? []))
      .catch(() => setClusters([]))
      .finally(() => setLoading(false));
  }, [days]);

  return (
    <div className="glass-card overflow-hidden">
      <div className="px-5 py-4 border-b border-border flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">Root Cause Clusters</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">
            Deviation patterns grouped by type and supplier
          </p>
        </div>
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value) as typeof days)}
          className="text-[12px] font-medium text-foreground rounded-lg px-3 py-1.5 bg-surfaceRaised border border-border focus:outline-none focus:ring-1 focus:ring-accent"
        >
          {DAY_OPTIONS.map((d) => (
            <option key={d} value={d}>{d}d</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="px-5 py-10 text-center text-xs text-mutedForeground">Loading clusters…</div>
      ) : clusters.length === 0 ? (
        <div className="px-5 py-10 text-center text-xs text-mutedForeground">
          No deviation clusters in the last {days} days
        </div>
      ) : (
        <div className="divide-y divide-border">
          {clusters.map((c, i) => {
            const critRatio = c.count > 0 ? c.critical_count / c.count : 0;
            const barColor = critRatio > 0.5 ? "#ef4444" : critRatio > 0.2 ? "#f59e0b" : "#0070F3";
            return (
              <div key={i} className="px-5 py-3.5 flex items-center gap-4">
                {/* Bar */}
                <div className="w-1.5 rounded-full self-stretch shrink-0" style={{ background: barColor, minHeight: 32 }} />

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[12px] font-semibold text-foreground">{typeLabel(c.type)}</span>
                    <span
                      className="text-[10px] font-medium px-1.5 py-0.5 rounded"
                      style={{ background: "rgba(0,112,243,0.06)", color: "#0070F3", border: "1px solid rgba(0,112,243,0.12)" }}
                    >
                      {c.supplier_id}
                    </span>
                  </div>
                  <p className="text-[11px] text-mutedForeground mt-0.5">
                    Last seen {daysAgo(c.last_seen)}
                  </p>
                </div>

                {/* Counts */}
                <div className="text-right shrink-0">
                  <p className="text-lg font-bold tabular-nums text-foreground">{c.count}</p>
                  {c.critical_count > 0 && (
                    <p className="text-[10px] font-medium text-destructive">{c.critical_count} critical</p>
                  )}
                </div>

                {/* Mini bar chart */}
                <div className="w-20 shrink-0 hidden sm:block">
                  <div className="h-1.5 rounded-full bg-border overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${Math.min(100, (c.count / Math.max(...clusters.map((x) => x.count))) * 100)}%`,
                        background: barColor,
                      }}
                    />
                  </div>
                  {c.critical_count > 0 && (
                    <div className="h-1 rounded-full bg-border overflow-hidden mt-0.5">
                      <div
                        className="h-full rounded-full bg-destructive transition-all"
                        style={{
                          width: `${Math.min(100, (c.critical_count / Math.max(...clusters.map((x) => x.count))) * 100)}%`,
                        }}
                      />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
