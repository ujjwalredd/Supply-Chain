"use client";

import { useEffect, useState } from "react";
import { fetchDeviationTrend } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

type TrendDay = {
  date: string;
  CRITICAL: number;
  HIGH: number;
  MEDIUM: number;
  total: number;
};

export function DeviationTrendChart() {
  const [data, setData] = useState<TrendDay[]>([]);

  useEffect(() => {
    fetchDeviationTrend(7).then(setData).catch(() => setData([]));
    const id = setInterval(
      () => fetchDeviationTrend(7).then(setData).catch(() => {}),
      60000
    );
    return () => clearInterval(id);
  }, []);

  const chartData = data.map((d) => ({
    ...d,
    label: new Date(d.date + "T12:00:00Z").toLocaleDateString("en-US", {
      weekday: "short",
      month: "numeric",
      day: "numeric",
    }),
  }));

  const total = data.reduce((s, d) => s + d.total, 0);

  return (
    <div
      className="rounded-xl overflow-hidden bg-surface border border-border"
      style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}
    >
      <div className="px-5 py-4 flex items-center justify-between border-b border-border">
        <div>
          <p className="text-sm font-semibold text-foreground">Deviation Trend</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">Alert volume — last 7 days</p>
        </div>
        {total > 0 && (
          <span className="text-[11px] text-mutedForeground">
            <span className="text-foreground font-semibold">{total}</span> total
          </span>
        )}
      </div>
      <div className="px-2 py-4">
        {chartData.length === 0 || total === 0 ? (
          <p className="text-xs text-mutedForeground px-3 py-8 text-center">
            No deviations in the last 7 days.
          </p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={chartData} margin={{ left: 0, right: 8, top: 4, bottom: 0 }}>
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 10, fill: "#94a3b8" }}
                  axisLine={false}
                  tickLine={false}
                  width={24}
                />
                <Tooltip
                  cursor={{ fill: "rgba(0,0,0,0.03)" }}
                  content={({ active, payload }) =>
                    active && payload?.[0] ? (
                      <div
                        className="rounded-lg px-3 py-2 text-xs"
                        style={{
                          background: "#ffffff",
                          border: "1px solid #e2e8f0",
                          boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                        }}
                      >
                        <p className="text-mutedForeground mb-1.5">{payload[0].payload.date}</p>
                        <p style={{ color: "#ef4444" }}>
                          Critical: {payload[0].payload.CRITICAL}
                        </p>
                        <p style={{ color: "#f59e0b" }}>High: {payload[0].payload.HIGH}</p>
                        <p style={{ color: "#6366f1" }}>Medium: {payload[0].payload.MEDIUM}</p>
                      </div>
                    ) : null
                  }
                />
                <Bar dataKey="CRITICAL" stackId="a" fill="#ef4444" maxBarSize={36} />
                <Bar dataKey="HIGH" stackId="a" fill="#f59e0b" maxBarSize={36} />
                <Bar
                  dataKey="MEDIUM"
                  stackId="a"
                  fill="#6366f1"
                  maxBarSize={36}
                  radius={[3, 3, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
            <div className="flex items-center gap-5 px-3 mt-1">
              {[
                { c: "#ef4444", l: "Critical" },
                { c: "#f59e0b", l: "High" },
                { c: "#6366f1", l: "Medium" },
              ].map((x) => (
                <div key={x.l} className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full shrink-0" style={{ background: x.c }} />
                  <span className="text-[10px] text-mutedForeground">{x.l}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
