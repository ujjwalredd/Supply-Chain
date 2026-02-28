"use client";

import { KPICards } from "@/components/KPICards";
import { DeviationFeed } from "@/components/DeviationFeed";
import { SupplierRisk } from "@/components/SupplierRisk";
import { OrderTable } from "@/components/OrderTable";
import { OntologyGraph } from "@/components/OntologyGraph";
import { ActionsLog } from "@/components/ActionsLog";
import { RiskForecast } from "@/components/RiskForecast";
import { SupplyChainGraph } from "@/components/SupplyChainGraph";
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
          <KPICards />
        </section>

        <div className="h-px bg-border mb-8" />

        <section className="mb-8 grid gap-6 lg:grid-cols-2">
          <DeviationFeed />
          <SupplierRisk />
        </section>

        <div className="h-px bg-border mb-8" />

        <section className="mb-8 grid gap-6 lg:grid-cols-2">
          <RiskForecast />
          <ActionsLog />
        </section>

        <div className="h-px bg-border mb-8" />

        <section className="mb-8">
          <OrderTable />
        </section>

        <div className="h-px bg-border mb-8" />

        <section className="mb-8">
          <SupplyChainGraph />
        </section>

        <div className="h-px bg-border mb-8" />

        <section className="pb-8">
          <OntologyGraph />
        </section>

      </div>
    </div>
  );
}
