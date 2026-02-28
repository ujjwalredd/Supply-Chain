"use client";

import { Suspense } from "react";
import { KPICards } from "@/components/KPICards";
import { DeviationFeed } from "@/components/DeviationFeed";
import { SupplierRisk } from "@/components/SupplierRisk";
import { OrderTable } from "@/components/OrderTable";
import { OntologyGraph } from "@/components/OntologyGraph";
import { ActionsLog } from "@/components/ActionsLog";
import { RiskForecast } from "@/components/RiskForecast";
import { SupplyChainGraph } from "@/components/SupplyChainGraph";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PanelSkeleton } from "@/components/PanelSkeleton";
import { useWebSocket } from "@/hooks/useWebSocket";

export default function ControlTowerPage() {
  const { connected } = useWebSocket();

  return (
    <div className="min-h-screen">
      <div className="max-w-screen-xl mx-auto px-6 py-8">

        <header className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-foreground">Supply Chain OS</h1>
            <p className="text-xs text-mutedForeground mt-0.5">Control Tower</p>
          </div>
          <div className="flex items-center gap-1.5">
            <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-success" : "bg-mutedForeground"}`} />
            <span className="text-xs text-mutedForeground">{connected ? "Live" : "Connecting"}</span>
          </div>
        </header>

        <section className="mb-8">
          <ErrorBoundary label="KPI Cards">
            <Suspense fallback={<PanelSkeleton rows={3} height="h-16" />}>
              <KPICards />
            </Suspense>
          </ErrorBoundary>
        </section>

        <div className="h-px bg-border mb-8" />

        <section className="mb-8 grid gap-6 lg:grid-cols-2">
          <ErrorBoundary label="Deviation Feed">
            <Suspense fallback={<PanelSkeleton rows={5} />}>
              <DeviationFeed />
            </Suspense>
          </ErrorBoundary>
          <ErrorBoundary label="Supplier Risk">
            <Suspense fallback={<PanelSkeleton rows={5} />}>
              <SupplierRisk />
            </Suspense>
          </ErrorBoundary>
        </section>

        <div className="h-px bg-border mb-8" />

        <section className="mb-8 grid gap-6 lg:grid-cols-2">
          <ErrorBoundary label="Risk Forecast">
            <Suspense fallback={<PanelSkeleton rows={6} />}>
              <RiskForecast />
            </Suspense>
          </ErrorBoundary>
          <ErrorBoundary label="Actions Log">
            <Suspense fallback={<PanelSkeleton rows={4} />}>
              <ActionsLog />
            </Suspense>
          </ErrorBoundary>
        </section>

        <div className="h-px bg-border mb-8" />

        <section className="mb-8">
          <ErrorBoundary label="Order Table">
            <Suspense fallback={<PanelSkeleton rows={8} />}>
              <OrderTable />
            </Suspense>
          </ErrorBoundary>
        </section>

        <div className="h-px bg-border mb-8" />

        <section className="mb-8">
          <ErrorBoundary label="Supply Chain Graph">
            <Suspense fallback={<PanelSkeleton rows={6} height="h-6" />}>
              <SupplyChainGraph />
            </Suspense>
          </ErrorBoundary>
        </section>

        <div className="h-px bg-border mb-8" />

        <section className="pb-8">
          <ErrorBoundary label="Ontology Graph">
            <Suspense fallback={<PanelSkeleton rows={5} height="h-5" />}>
              <OntologyGraph />
            </Suspense>
          </ErrorBoundary>
        </section>

      </div>
    </div>
  );
}
