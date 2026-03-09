"use client";

import { Suspense } from "react";
import { DeviationFeed } from "@/components/DeviationFeed";
import { ActionsLog } from "@/components/ActionsLog";
import { DeviationClusters } from "@/components/DeviationClusters";
import { BulkTriagePanel } from "@/components/BulkTriagePanel";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PanelSkeleton } from "@/components/PanelSkeleton";

export default function AlertsPage() {
  return (
    <div className="px-8 py-7 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Deviations</h1>
        <p className="text-sm text-mutedForeground mt-0.5">
          Active supply chain alerts — click any deviation to trigger AI analysis
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-5">
          <ErrorBoundary label="Deviation Feed">
            <Suspense fallback={<PanelSkeleton rows={10} />}>
              <DeviationFeed />
            </Suspense>
          </ErrorBoundary>

          <ErrorBoundary label="Bulk Triage">
            <BulkTriagePanel />
          </ErrorBoundary>
        </div>

        <div className="space-y-5">
          <ErrorBoundary label="Actions Log">
            <Suspense fallback={<PanelSkeleton rows={8} />}>
              <ActionsLog />
            </Suspense>
          </ErrorBoundary>

          <ErrorBoundary label="Deviation Clusters">
            <Suspense fallback={<PanelSkeleton rows={6} />}>
              <DeviationClusters />
            </Suspense>
          </ErrorBoundary>
        </div>
      </div>
    </div>
  );
}
