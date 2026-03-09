"use client";

import { Suspense } from "react";
import { KPICards } from "@/components/KPICards";
import { QueryBox } from "@/components/QueryBox";
import { DeviationFeed } from "@/components/DeviationFeed";
import { ActionsLog } from "@/components/ActionsLog";
import { RiskForecast } from "@/components/RiskForecast";
import { DeviationTrendChart } from "@/components/DeviationTrendChart";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PanelSkeleton } from "@/components/PanelSkeleton";

function PageHeader({ title, description }: { title: string; description: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-xl font-semibold text-foreground">{title}</h1>
      <p className="text-sm text-mutedForeground mt-0.5">{description}</p>
    </div>
  );
}

function SectionTitle({ title }: { title: string }) {
  return (
    <h2 className="text-[11px] font-semibold text-mutedForeground uppercase tracking-[0.08em] mb-3">
      {title}
    </h2>
  );
}

export default function OverviewPage() {
  return (
    <div className="px-8 py-7 max-w-[1400px]">
      <PageHeader
        title="Control Tower"
        description="Real-time visibility into your supply chain operations"
      />

      {/* KPI Row */}
      <div className="mb-7">
        <ErrorBoundary label="KPI Cards">
          <Suspense fallback={<PanelSkeleton rows={1} height="h-24" />}>
            <KPICards />
          </Suspense>
        </ErrorBoundary>
      </div>

      {/* Query Box */}
      <div className="mb-7">
        <ErrorBoundary label="Query Box">
          <QueryBox />
        </ErrorBoundary>
      </div>

      {/* Live Operations */}
      <div className="mb-7">
        <SectionTitle title="Live Operations" />
        <div className="grid gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <ErrorBoundary label="Deviation Feed">
              <Suspense fallback={<PanelSkeleton rows={6} />}>
                <DeviationFeed />
              </Suspense>
            </ErrorBoundary>
          </div>
          <div>
            <ErrorBoundary label="Actions Log">
              <Suspense fallback={<PanelSkeleton rows={6} />}>
                <ActionsLog />
              </Suspense>
            </ErrorBoundary>
          </div>
        </div>
      </div>

      {/* Analytics */}
      <div className="mb-7">
        <SectionTitle title="Analytics" />
        <div className="grid gap-5 lg:grid-cols-2">
          <ErrorBoundary label="Deviation Trend">
            <Suspense fallback={<PanelSkeleton rows={5} />}>
              <DeviationTrendChart />
            </Suspense>
          </ErrorBoundary>
          <ErrorBoundary label="Risk Forecast">
            <Suspense fallback={<PanelSkeleton rows={5} />}>
              <RiskForecast />
            </Suspense>
          </ErrorBoundary>
        </div>
      </div>
    </div>
  );
}
