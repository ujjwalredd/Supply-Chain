"use client";

import { Suspense } from "react";
import { ActionsLog } from "@/components/ActionsLog";
import { AuditTrail } from "@/components/AuditTrail";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PanelSkeleton } from "@/components/PanelSkeleton";

export default function ActionsPage() {
  return (
    <div className="px-8 py-7 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Autonomous Actions</h1>
        <p className="text-sm text-mutedForeground mt-0.5">
          AI-recommended actions and full decision trail — every recommendation logged with context and outcome
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <ErrorBoundary label="Actions Log">
            <Suspense fallback={<PanelSkeleton rows={10} />}>
              <ActionsLog />
            </Suspense>
          </ErrorBoundary>
        </div>

        <div className="lg:col-span-2">
          <ErrorBoundary label="Audit Trail">
            <Suspense fallback={<PanelSkeleton rows={10} />}>
              <AuditTrail />
            </Suspense>
          </ErrorBoundary>
        </div>
      </div>
    </div>
  );
}
