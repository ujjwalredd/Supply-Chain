"use client";

import { Suspense } from "react";
import { SupplierScorecard } from "@/components/SupplierScorecard";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PanelSkeleton } from "@/components/PanelSkeleton";

export default function ScorecardPage() {
  return (
    <div className="px-8 py-7 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Supplier Scorecard</h1>
        <p className="text-sm text-mutedForeground mt-0.5">
          Weekly performance trends — on-time rate, delay patterns, and deviation frequency per supplier
        </p>
      </div>

      <div className="max-w-3xl">
        <ErrorBoundary label="Supplier Scorecard">
          <Suspense fallback={<PanelSkeleton rows={8} />}>
            <SupplierScorecard />
          </Suspense>
        </ErrorBoundary>
      </div>
    </div>
  );
}
