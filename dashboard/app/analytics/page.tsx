"use client";

import { Suspense } from "react";
import { DeviationTrendChart } from "@/components/DeviationTrendChart";
import { RiskForecast } from "@/components/RiskForecast";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PanelSkeleton } from "@/components/PanelSkeleton";

export default function AnalyticsPage() {
  return (
    <div className="px-8 py-7 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Analytics & Forecasts</h1>
        <p className="text-sm text-mutedForeground mt-0.5">
          7-day deviation trend and ML-scored orders most likely to fail
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <ErrorBoundary label="Deviation Trend">
          <Suspense fallback={<PanelSkeleton rows={6} />}>
            <DeviationTrendChart />
          </Suspense>
        </ErrorBoundary>
        <ErrorBoundary label="Risk Forecast">
          <Suspense fallback={<PanelSkeleton rows={6} />}>
            <RiskForecast />
          </Suspense>
        </ErrorBoundary>
      </div>
    </div>
  );
}
