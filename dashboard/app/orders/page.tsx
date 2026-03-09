"use client";

import { Suspense } from "react";
import { OrderTable } from "@/components/OrderTable";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PanelSkeleton } from "@/components/PanelSkeleton";

export default function OrdersPage() {
  return (
    <div className="px-8 py-7 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Order Pipeline</h1>
        <p className="text-sm text-mutedForeground mt-0.5">
          All orders — filter by status, supplier, or product and export to CSV
        </p>
      </div>

      <ErrorBoundary label="Order Table">
        <Suspense fallback={<PanelSkeleton rows={10} height="h-5" />}>
          <OrderTable />
        </Suspense>
      </ErrorBoundary>
    </div>
  );
}
