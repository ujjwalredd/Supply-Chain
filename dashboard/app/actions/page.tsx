"use client";

import { Suspense } from "react";
import { ActionsLog } from "@/components/ActionsLog";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PanelSkeleton } from "@/components/PanelSkeleton";

export default function ActionsPage() {
  return (
    <div className="px-8 py-7 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Autonomous Actions</h1>
        <p className="text-sm text-mutedForeground mt-0.5">
          AI-recommended actions — auto-executed when confidence exceeds threshold
        </p>
      </div>

      <div className="max-w-2xl">
        <ErrorBoundary label="Actions Log">
          <Suspense fallback={<PanelSkeleton rows={10} />}>
            <ActionsLog />
          </Suspense>
        </ErrorBoundary>
      </div>
    </div>
  );
}
