"use client";

import { useEffect, useState } from "react";
import { fetchOrders } from "@/lib/api";
import { Download, Clock } from "lucide-react";
import { OrderTimeline } from "@/components/OrderTimeline";

type Order = {
  order_id: string;
  supplier_id: string;
  product: string;
  order_value: number;
  delay_days: number;
  status: string;
};

const statusBadge: Record<string, { bg: string; color: string }> = {
  DELAYED:    { bg: "rgba(239,68,68,0.08)",   color: "#ef4444" },
  DELIVERED:  { bg: "rgba(16,185,129,0.08)",  color: "#059669" },
  IN_TRANSIT: { bg: "rgba(0,112,243,0.08)",   color: "#0070F3" },
  PENDING:    { bg: "rgba(100,116,139,0.06)", color: "#64748b" },
  CANCELLED:  { bg: "rgba(100,116,139,0.06)", color: "#64748b" },
};

function exportCSV(orders: Order[]) {
  const header = ["Order ID", "Supplier", "Product", "Order Value", "Delay Days", "Status"];
  const rows = orders.map((o) => [
    o.order_id,
    o.supplier_id,
    o.product,
    (o.order_value ?? 0).toFixed(2),
    String(o.delay_days ?? 0),
    o.status,
  ]);
  const csv = [header, ...rows]
    .map((r) => r.map((v) => `"${v.replace(/"/g, '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `orders-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function OrderTable() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [timelineOrderId, setTimelineOrderId] = useState<string | null>(null);

  useEffect(() => {
    const params: Record<string, string> = { limit: "50" };
    if (statusFilter) params.status = statusFilter;
    fetchOrders(params)
      .then(setOrders)
      .catch(() => setOrders([]));
  }, [statusFilter]);

  return (
    <>
    {timelineOrderId && (
      <OrderTimeline orderId={timelineOrderId} onClose={() => setTimelineOrderId(null)} />
    )}
    <div
      className="rounded-xl overflow-hidden bg-surface border border-border"
      style={{ boxShadow: "0 1px 3px rgba(0,0,0,0.06)" }}
    >
      {/* Header */}
      <div className="px-5 py-4 flex items-center justify-between border-b border-border">
        <div>
          <p className="text-sm font-semibold text-foreground">Orders</p>
          <p className="text-[11px] text-mutedForeground mt-0.5">{orders.length} orders shown</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => exportCSV(orders)}
            disabled={orders.length === 0}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-colors disabled:opacity-40 hover:bg-muted"
            style={{ background: "rgba(0,112,243,0.08)", color: "#0070F3", border: "1px solid rgba(0,112,243,0.15)" }}
            title="Export visible orders as CSV"
          >
            <Download className="h-3 w-3" />
            Export CSV
          </button>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-[11px] font-medium text-mutedForeground rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-accent bg-surfaceRaised border border-border"
            aria-label="Filter by status"
          >
            <option value="">All statuses</option>
            <option value="PENDING">Pending</option>
            <option value="IN_TRANSIT">In Transit</option>
            <option value="DELIVERED">Delivered</option>
            <option value="DELAYED">Delayed</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>
      </div>

      <div className="overflow-x-auto max-h-[380px] overflow-y-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-surfaceRaised">
            <tr className="border-b border-border">
              {["Order ID", "Supplier", "Product", "Value", "Delay", "Status", ""].map((h, i) => (
                <th
                  key={h}
                  className={`py-2.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-mutedForeground ${i >= 3 && i !== 5 ? "text-right" : "text-left"}`}
                  style={{ padding: "10px 16px" }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {orders.map((o, idx) => {
              const badge = statusBadge[o.status] ?? statusBadge.PENDING;
              return (
                <tr
                  key={o.order_id}
                  className="hover:bg-surfaceRaised transition-colors"
                  style={{ borderBottom: idx < orders.length - 1 ? "1px solid #f1f5f9" : "none" }}
                >
                  <td className="px-4 py-3 font-mono text-[11px] text-mutedForeground">{o.order_id}</td>
                  <td className="px-4 py-3 text-xs text-foreground">{o.supplier_id}</td>
                  <td className="px-4 py-3 text-xs text-foreground max-w-[160px] truncate">{o.product}</td>
                  <td className="px-4 py-3 text-right text-xs tabular-nums text-foreground font-medium">
                    ${(o.order_value ?? 0).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right text-xs tabular-nums">
                    <span style={{ color: (o.delay_days ?? 0) > 0 ? "#d97706" : "#94a3b8" }}>
                      {o.delay_days ?? 0}d
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wide"
                      style={{ background: badge.bg, color: badge.color }}
                    >
                      {o.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => setTimelineOrderId(o.order_id)}
                      className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium text-mutedForeground hover:text-foreground hover:bg-surfaceRaised transition-colors border border-transparent hover:border-border"
                    >
                      <Clock className="h-3 w-3" />
                      Timeline
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {orders.length === 0 && (
          <p className="text-xs text-mutedForeground px-5 py-8">No orders found.</p>
        )}
      </div>
    </div>
    </>
  );
}
