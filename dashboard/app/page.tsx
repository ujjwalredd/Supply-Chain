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

function Section({ title, children, cols = 1 }: { title: string; children: React.ReactNode; cols?: 1 | 2 }) {
  return (
    <section className="mb-8">
      <h2 className="text-[11px] font-medium uppercase tracking-[0.1em] text-mutedForeground mb-4 px-0.5">
        {title}
      </h2>
      <div className={cols === 2 ? "grid gap-4 lg:grid-cols-2" : ""}>
        {children}
      </div>
    </section>
  );
}

export default function ControlTowerPage() {
  const { connected } = useWebSocket();

  return (
    <div className="min-h-screen bg-background">
      {/* Top nav */}
      <nav className="sticky top-0 z-40 border-b border-border bg-background/90 backdrop-blur-sm">
        <div className="max-w-screen-xl mx-auto px-6 h-12 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-6 w-6 rounded-md bg-accent/20 border border-accent/30 flex items-center justify-center">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M6 0.5L11 3.25V8.75L6 11.5L1 8.75V3.25L6 0.5Z" stroke="#7c6af7" strokeWidth="1.2" strokeLinejoin="round"/>
                <circle cx="6" cy="6" r="1.5" fill="#7c6af7"/>
              </svg>
            </div>
            <span className="text-[13px] font-semibold text-foreground tracking-tight">Supply Chain OS</span>
            <span className="text-mutedForeground text-[13px]">/</span>
            <span className="text-[13px] text-mutedForeground">Control Tower</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[11px] text-mutedForeground hidden sm:block">
              {new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
            </span>
            {connected ? (
              <div className="flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-60" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-success live-dot" />
                </span>
                <span className="text-[11px] font-medium text-success">Live</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-mutedForeground opacity-50" />
                <span className="text-[11px] text-mutedForeground">Offline</span>
              </div>
            )}
          </div>
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-screen-xl mx-auto px-6 py-8">

        {/* KPIs */}
        <div className="mb-8">
          <ErrorBoundary label="KPI Cards">
            <Suspense fallback={<PanelSkeleton rows={2} height="h-10" />}>
              <KPICards />
            </Suspense>
          </ErrorBoundary>
        </div>

        {/* Signals row */}
        <Section title="Signals" cols={2}>
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
        </Section>

        {/* Forecast + Actions */}
        <Section title="Forecast & Actions" cols={2}>
          <ErrorBoundary label="Risk Forecast">
            <Suspense fallback={<PanelSkeleton rows={5} />}>
              <RiskForecast />
            </Suspense>
          </ErrorBoundary>
          <ErrorBoundary label="Actions Log">
            <Suspense fallback={<PanelSkeleton rows={5} />}>
              <ActionsLog />
            </Suspense>
          </ErrorBoundary>
        </Section>

        {/* Orders */}
        <Section title="Orders">
          <ErrorBoundary label="Order Table">
            <Suspense fallback={<PanelSkeleton rows={7} height="h-5" />}>
              <OrderTable />
            </Suspense>
          </ErrorBoundary>
        </Section>

        {/* Network */}
        <Section title="Supply Network">
          <ErrorBoundary label="Supply Chain Graph">
            <Suspense fallback={<PanelSkeleton rows={5} height="h-5" />}>
              <SupplyChainGraph />
            </Suspense>
          </ErrorBoundary>
        </Section>

        {/* Ontology */}
        <Section title="Ontology Constraints">
          <ErrorBoundary label="Ontology Graph">
            <Suspense fallback={<PanelSkeleton rows={4} height="h-5" />}>
              <OntologyGraph />
            </Suspense>
          </ErrorBoundary>
        </Section>

      </main>
    </div>
  );
}
