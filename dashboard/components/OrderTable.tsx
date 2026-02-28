"use client";

import { useEffect, useState } from "react";
import { fetchOrders } from "@/lib/api";

type Order = {
  order_id: string;
  supplier_id: string;
  product: string;
  order_value: number;
  delay_days: number;
  status: string;
};

const statusStyle: Record<string, string> = {
  DELAYED: "text-destructive",
  DELIVERED: "text-success",
  IN_TRANSIT: "text-accent",
};

export function OrderTable() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>("");

  useEffect(() => {
    const params: Record<string, string> = { limit: "50" };
    if (statusFilter) params.status = statusFilter;
    fetchOrders(params)
      .then(setOrders)
      .catch(() => setOrders([]));
  }, [statusFilter]);

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <p className="text-sm font-medium text-foreground">Orders</p>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-background border border-border rounded px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-accent"
          aria-label="Filter by status"
        >
          <option value="">All</option>
          <option value="PENDING">Pending</option>
          <option value="IN_TRANSIT">In Transit</option>
          <option value="DELIVERED">Delivered</option>
          <option value="DELAYED">Delayed</option>
          <option value="CANCELLED">Cancelled</option>
        </select>
      </div>
      <div className="overflow-x-auto max-h-[300px] overflow-y-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left px-4 py-2.5 font-medium text-mutedForeground">Order</th>
              <th className="text-left px-4 py-2.5 font-medium text-mutedForeground">Supplier</th>
              <th className="text-left px-4 py-2.5 font-medium text-mutedForeground">Product</th>
              <th className="text-right px-4 py-2.5 font-medium text-mutedForeground">Value</th>
              <th className="text-right px-4 py-2.5 font-medium text-mutedForeground">Delay</th>
              <th className="text-left px-4 py-2.5 font-medium text-mutedForeground">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {orders.map((o) => (
              <tr key={o.order_id} className="hover:bg-muted transition-colors">
                <td className="px-4 py-2.5 font-mono text-mutedForeground">{o.order_id}</td>
                <td className="px-4 py-2.5 text-foreground">{o.supplier_id}</td>
                <td className="px-4 py-2.5 text-foreground">{o.product}</td>
                <td className="px-4 py-2.5 text-right tabular-nums text-foreground">
                  ${(o.order_value ?? 0).toLocaleString()}
                </td>
                <td className="px-4 py-2.5 text-right tabular-nums">
                  <span className={(o.delay_days ?? 0) > 0 ? "text-warning" : "text-mutedForeground"}>
                    {o.delay_days ?? 0}d
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <span className={statusStyle[o.status] ?? "text-mutedForeground"}>
                    {o.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {orders.length === 0 && (
          <p className="text-xs text-mutedForeground px-4 py-6">No orders found.</p>
        )}
      </div>
    </div>
  );
}
