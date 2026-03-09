"use client";

import { useEffect, useState } from "react";
import { fetchOrderTimeline } from "@/lib/api";
import { X } from "lucide-react";

type TimelineEvent = {
  event: string;
  timestamp: string;
  label: string;
  deviation_id?: string;
  severity?: string;
  note?: string;
};

type TimelineData = {
  order_id: string;
  status: string;
  supplier_id: string;
  product: string;
  order_value: number;
  events: TimelineEvent[];
};

function eventColor(event: string, severity?: string) {
  if (event === "DEVIATION") {
    return severity === "CRITICAL" ? "#ef4444"
      : severity === "HIGH" ? "#d97706"
      : "#0070F3";
  }
  if (event === "DELIVERED") return "#10b981";
  if (event === "DELAY_CONFIRMED") return "#ef4444";
  if (event === "ORDER_PLACED") return "#0070F3";
  return "#94a3b8";
}

function formatTs(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function OrderTimeline({
  orderId,
  onClose,
}: {
  orderId: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<TimelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchOrderTimeline(orderId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [orderId]);

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
      <div
        className="fixed right-0 top-0 bottom-0 z-50 flex flex-col w-full max-w-[420px] bg-surface"
        style={{ borderLeft: "1px solid #e2e8f0", boxShadow: "-4px 0 24px rgba(0,0,0,0.08)" }}
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 shrink-0 border-b border-border">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground font-mono truncate">{orderId}</p>
            {data && (
              <p className="text-[11px] text-mutedForeground mt-0.5">
                {data.product} · {data.supplier_id} · ${data.order_value.toLocaleString()}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-mutedForeground hover:text-foreground hover:bg-surfaceRaised transition-colors shrink-0 ml-3"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-5 py-5">
          {loading && (
            <p className="text-xs text-mutedForeground text-center mt-10">Loading timeline…</p>
          )}
          {error && (
            <div
              className="p-3 rounded-lg text-xs text-destructive"
              style={{ background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.15)" }}
            >
              {error}
            </div>
          )}
          {data && (
            <div className="relative">
              {/* Vertical line */}
              <div className="absolute left-[7px] top-2 bottom-2 w-px bg-border" />

              <div className="space-y-0">
                {data.events.map((ev, i) => {
                  const color = eventColor(ev.event, ev.severity);
                  return (
                    <div key={i} className="relative flex gap-4 pb-6 last:pb-0">
                      {/* Dot */}
                      <div className="relative shrink-0 mt-1">
                        <div
                          className="h-3.5 w-3.5 rounded-full ring-2 ring-white z-10 relative"
                          style={{ background: color }}
                        />
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0 -mt-0.5">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-[12px] font-semibold text-foreground">{ev.label}</p>
                            {ev.note && (
                              <p className="text-[11px] text-mutedForeground mt-0.5">{ev.note}</p>
                            )}
                            {ev.deviation_id && (
                              <span
                                className="inline-flex items-center mt-1 px-1.5 py-0.5 rounded text-[10px] font-medium"
                                style={{
                                  background: `${color}10`,
                                  color,
                                  border: `1px solid ${color}25`,
                                }}
                              >
                                {ev.severity} · {ev.deviation_id.slice(0, 8)}
                              </span>
                            )}
                          </div>
                          <time className="text-[10px] text-mutedForeground whitespace-nowrap mt-0.5 shrink-0">
                            {formatTs(ev.timestamp)}
                          </time>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
