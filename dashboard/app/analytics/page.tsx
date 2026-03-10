"use client";

import { Suspense } from "react";
import { DeviationTrendChart } from "@/components/DeviationTrendChart";
import { RiskForecast } from "@/components/RiskForecast";
import { ProactiveDelayPanel } from "@/components/ProactiveDelayPanel";
import { CostAnalyticsPanel } from "@/components/CostAnalyticsPanel";
import { SupplierBenchmark } from "@/components/SupplierBenchmark";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PanelSkeleton } from "@/components/PanelSkeleton";

export default function AnalyticsPage() {
  return (
    <div className="px-8 py-7 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Analytics & Forecasts</h1>
        <p className="text-sm text-mutedForeground mt-0.5">
          Proactive risk scoring, cost exposure, supplier benchmarks, and deviation trends
        </p>
      </div>

      <div className="space-y-5">
        {/* Top row — proactive delay predictions (full width) */}
        <ErrorBoundary label="Proactive Delay Predictions">
          <Suspense fallback={<PanelSkeleton rows={8} />}>
            <ProactiveDelayPanel />
          </Suspense>
        </ErrorBoundary>

        {/* Second row — trend + risk side by side */}
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

        {/* Cost analytics — full width */}
        <ErrorBoundary label="Cost Analytics">
          <Suspense fallback={<PanelSkeleton rows={8} />}>
            <CostAnalyticsPanel />
          </Suspense>
        </ErrorBoundary>

        {/* Supplier benchmarks — full width */}
        <ErrorBoundary label="Supplier Benchmarks">
          <Suspense fallback={<PanelSkeleton rows={8} />}>
            <SupplierBenchmark />
          </Suspense>
        </ErrorBoundary>
      </div>
    </div>
  );
}
