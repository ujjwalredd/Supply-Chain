"use client";

import { Suspense } from "react";
import { KPICards } from "@/components/KPICards";
import { QueryBox } from "@/components/QueryBox";
import { DeviationFeed } from "@/components/DeviationFeed";
import { SupplierRisk } from "@/components/SupplierRisk";
import { OrderTable } from "@/components/OrderTable";
import { OntologyGraph } from "@/components/OntologyGraph";
import { ActionsLog } from "@/components/ActionsLog";
import { RiskForecast } from "@/components/RiskForecast";
import { SupplyChainGraph } from "@/components/SupplyChainGraph";
import { DeviationTrendChart } from "@/components/DeviationTrendChart";
import { SupplierHeatmap } from "@/components/SupplierHeatmap";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PanelSkeleton } from "@/components/PanelSkeleton";
import { useWebSocket } from "@/hooks/useWebSocket";

function SectionHeader({
  title,
  description,
  icon,
}: {
  title: string;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-3 mb-5">
      <div
        className="flex items-center justify-center h-8 w-8 rounded-lg shrink-0"
        style={{ background: "rgba(124,106,247,0.12)", border: "1px solid rgba(124,106,247,0.2)" }}
      >
        {icon}
      </div>
      <div>
        <h2 className="text-sm font-semibold text-foreground leading-none">{title}</h2>
        <p className="text-[11px] text-mutedForeground mt-0.5">{description}</p>
      </div>
    </div>
  );
}

function Divider() {
  return <div className="mb-10" />;
}

export default function ControlTowerPage() {
  const { connected } = useWebSocket();

  return (
    <div className="min-h-screen bg-background">
      {/* ── Top nav ──────────────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur-sm">
        <div className="max-w-screen-xl mx-auto px-6 h-13 flex items-center justify-between" style={{ height: "52px" }}>
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div
              className="h-7 w-7 rounded-lg flex items-center justify-center shrink-0"
              style={{ background: "rgba(124,106,247,0.15)", border: "1px solid rgba(124,106,247,0.25)" }}
            >
              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                <path d="M6.5 0.7L12 3.6V9.4L6.5 12.3L1 9.4V3.6L6.5 0.7Z" stroke="#7c6af7" strokeWidth="1.2" strokeLinejoin="round"/>
                <circle cx="6.5" cy="6.5" r="1.8" fill="#7c6af7"/>
              </svg>
            </div>
            <div>
              <span className="text-[13px] font-semibold text-foreground tracking-tight">Supply Chain OS</span>
              <span className="text-mutedForeground text-[13px] mx-2">/</span>
              <span className="text-[13px] text-mutedForeground">Control Tower</span>
            </div>
          </div>

          {/* Right side */}
          <div className="flex items-center gap-4">
            {/* Date */}
            <span className="text-[11px] text-mutedForeground hidden md:block">
              {new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" })}
            </span>

            {/* Docs link */}
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:flex items-center gap-1.5 text-[11px] text-mutedForeground hover:text-foreground transition-colors"
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <rect x="1" y="1" width="8" height="8" rx="1" stroke="currentColor" strokeWidth="1"/>
                <path d="M3 5h4M3 3.5h4M3 6.5h2.5" stroke="currentColor" strokeWidth="0.8" strokeLinecap="round"/>
              </svg>
              API Docs
            </a>

            {/* WebSocket status */}
            {connected ? (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full" style={{ background: "rgba(52,211,153,0.1)", border: "1px solid rgba(52,211,153,0.2)" }}>
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-60" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-success" />
                </span>
                <span className="text-[11px] font-medium text-success">Live</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)" }}>
                <span className="h-1.5 w-1.5 rounded-full bg-mutedForeground opacity-40" />
                <span className="text-[11px] text-mutedForeground">Offline</span>
              </div>
            )}
          </div>
        </div>
      </nav>

      {/* ── Main content ─────────────────────────────────────────────────────── */}
      <main className="max-w-screen-xl mx-auto px-6 py-8">

        {/* ── KPI Cards ──────────────────────────────────────────────────────── */}
        <div className="mb-6">
          <ErrorBoundary label="KPI Cards">
            <Suspense fallback={<PanelSkeleton rows={1} height="h-20" />}>
              <KPICards />
            </Suspense>
          </ErrorBoundary>
        </div>

        {/* ── Natural Language Query ─────────────────────────────────────────── */}
        <div className="mb-10">
          <ErrorBoundary label="Query Box">
            <QueryBox />
          </ErrorBoundary>
        </div>

        {/* ── Operations: Live signals + execution log ────────────────────────
            Layout: 3 columns on lg+ (Deviations takes 2, Actions takes 1)        */}
        <section className="mb-10">
          <SectionHeader
            title="Live Operations"
            description="Real-time deviation feed with AI-guided autonomous actions"
            icon={
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="5.5" stroke="#7c6af7" strokeWidth="1.2"/>
                <path d="M7 4v3l2 1" stroke="#7c6af7" strokeWidth="1.2" strokeLinecap="round"/>
              </svg>
            }
          />
          <div className="grid gap-4 lg:grid-cols-3">
            {/* Deviations — wide column */}
            <div className="lg:col-span-2">
              <ErrorBoundary label="Deviation Feed">
                <Suspense fallback={<PanelSkeleton rows={6} />}>
                  <DeviationFeed />
                </Suspense>
              </ErrorBoundary>
            </div>
            {/* Actions Log — narrow column */}
            <div>
              <ErrorBoundary label="Actions Log">
                <Suspense fallback={<PanelSkeleton rows={6} />}>
                  <ActionsLog />
                </Suspense>
              </ErrorBoundary>
            </div>
          </div>
        </section>

        <Divider />

        {/* ── Supplier Intelligence ───────────────────────────────────────────
            Layout: 2 columns — bar chart + health heatmap                         */}
        <section className="mb-10">
          <SectionHeader
            title="Supplier Intelligence"
            description="Trust scores, delay rates, and dependency concentration by supplier"
            icon={
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M2 10L5 6.5L8 8L12 4" stroke="#7c6af7" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="5" cy="6.5" r="1" fill="#7c6af7"/>
                <circle cx="8" cy="8" r="1" fill="#7c6af7"/>
                <circle cx="12" cy="4" r="1" fill="#7c6af7"/>
              </svg>
            }
          />
          <div className="grid gap-4 lg:grid-cols-2">
            <ErrorBoundary label="Supplier Risk Chart">
              <Suspense fallback={<PanelSkeleton rows={5} />}>
                <SupplierRisk />
              </Suspense>
            </ErrorBoundary>
            <ErrorBoundary label="Supplier Health Heatmap">
              <Suspense fallback={<PanelSkeleton rows={6} />}>
                <SupplierHeatmap />
              </Suspense>
            </ErrorBoundary>
          </div>
        </section>

        <Divider />

        {/* ── Analytics ──────────────────────────────────────────────────────
            Layout: 2 columns — 7-day trend + at-risk order forecast               */}
        <section className="mb-10">
          <SectionHeader
            title="Analytics & Forecasts"
            description="7-day deviation trend and ML-scored orders most likely to fail"
            icon={
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <rect x="2" y="8" width="2" height="4" rx="0.5" fill="#7c6af7" opacity="0.5"/>
                <rect x="5.5" y="5" width="2" height="7" rx="0.5" fill="#7c6af7" opacity="0.7"/>
                <rect x="9" y="2" width="2" height="10" rx="0.5" fill="#7c6af7"/>
              </svg>
            }
          />
          <div className="grid gap-4 lg:grid-cols-2">
            <ErrorBoundary label="Deviation Trend">
              <Suspense fallback={<PanelSkeleton rows={5} height="h-5" />}>
                <DeviationTrendChart />
              </Suspense>
            </ErrorBoundary>
            <ErrorBoundary label="Risk Forecast">
              <Suspense fallback={<PanelSkeleton rows={5} />}>
                <RiskForecast />
              </Suspense>
            </ErrorBoundary>
          </div>
        </section>

        <Divider />

        {/* ── Order Pipeline ─────────────────────────────────────────────────
            Full-width order table with search, filter, and CSV export             */}
        <section className="mb-10">
          <SectionHeader
            title="Order Pipeline"
            description="All orders — filter by status, supplier, or product and export to CSV"
            icon={
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <rect x="2" y="2" width="10" height="10" rx="1.5" stroke="#7c6af7" strokeWidth="1.2"/>
                <path d="M2 5.5h10" stroke="#7c6af7" strokeWidth="0.8"/>
                <path d="M2 8.5h10" stroke="#7c6af7" strokeWidth="0.8"/>
                <path d="M5.5 5.5v6.5" stroke="#7c6af7" strokeWidth="0.8"/>
              </svg>
            }
          />
          <ErrorBoundary label="Order Table">
            <Suspense fallback={<PanelSkeleton rows={8} height="h-5" />}>
              <OrderTable />
            </Suspense>
          </ErrorBoundary>
        </section>

        <Divider />

        {/* ── Network & Rules ────────────────────────────────────────────────
            Layout: 2 columns — supply network topology + ontology constraints     */}
        <section className="mb-10">
          <SectionHeader
            title="Network & Business Rules"
            description="Supply network topology (plant → port routing) and active ontology constraints"
            icon={
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="3" cy="7" r="1.5" stroke="#7c6af7" strokeWidth="1.2"/>
                <circle cx="11" cy="3" r="1.5" stroke="#7c6af7" strokeWidth="1.2"/>
                <circle cx="11" cy="11" r="1.5" stroke="#7c6af7" strokeWidth="1.2"/>
                <path d="M4.5 6.5L9.5 3.5M4.5 7.5L9.5 10.5" stroke="#7c6af7" strokeWidth="0.9" strokeLinecap="round"/>
              </svg>
            }
          />
          <div className="grid gap-4 lg:grid-cols-2">
            <ErrorBoundary label="Supply Chain Graph">
              <Suspense fallback={<PanelSkeleton rows={5} height="h-5" />}>
                <SupplyChainGraph />
              </Suspense>
            </ErrorBoundary>
            <ErrorBoundary label="Ontology Constraints">
              <Suspense fallback={<PanelSkeleton rows={4} height="h-5" />}>
                <OntologyGraph />
              </Suspense>
            </ErrorBoundary>
          </div>
        </section>

      </main>

      {/* ── Footer ───────────────────────────────────────────────────────────── */}
      <footer className="border-t border-border mt-4 py-5" style={{ borderColor: "rgba(255,255,255,0.06)" }}>
        <div className="max-w-screen-xl mx-auto px-6 flex items-center justify-between">
          <span className="text-[11px] text-mutedForeground">Supply Chain AI OS — v4.0</span>
          <div className="flex items-center gap-4">
            <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer" className="text-[11px] text-mutedForeground hover:text-foreground transition-colors">API</a>
            <a href="http://localhost:3001" target="_blank" rel="noopener noreferrer" className="text-[11px] text-mutedForeground hover:text-foreground transition-colors">Dagster</a>
            <a href="http://localhost:3002" target="_blank" rel="noopener noreferrer" className="text-[11px] text-mutedForeground hover:text-foreground transition-colors">Grafana</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
