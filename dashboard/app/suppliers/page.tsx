"use client";

import { Suspense } from "react";
import { SupplierRisk } from "@/components/SupplierRisk";
import { SupplierHeatmap } from "@/components/SupplierHeatmap";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PanelSkeleton } from "@/components/PanelSkeleton";

export default function SuppliersPage() {
  return (
    <div className="px-8 py-7 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Supplier Intelligence</h1>
        <p className="text-sm text-mutedForeground mt-0.5">
          Trust scores, delay rates, and dependency concentration by supplier
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-2 mb-5">
        <ErrorBoundary label="Supplier Risk Chart">
          <Suspense fallback={<PanelSkeleton rows={6} />}>
            <SupplierRisk />
          </Suspense>
        </ErrorBoundary>
        <ErrorBoundary label="Supplier Health Heatmap">
          <Suspense fallback={<PanelSkeleton rows={6} />}>
            <SupplierHeatmap />
          </Suspense>
        </ErrorBoundary>
      </div>
    </div>
  );
}
