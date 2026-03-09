"use client";

import { Suspense } from "react";
import { SupplyChainGraph } from "@/components/SupplyChainGraph";
import { OntologyGraph } from "@/components/OntologyGraph";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PanelSkeleton } from "@/components/PanelSkeleton";

export default function NetworkPage() {
  return (
    <div className="px-8 py-7 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Network & Business Rules</h1>
        <p className="text-sm text-mutedForeground mt-0.5">
          Supply network topology and active ontology constraints
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <ErrorBoundary label="Supply Chain Graph">
          <Suspense fallback={<PanelSkeleton rows={6} />}>
            <SupplyChainGraph />
          </Suspense>
        </ErrorBoundary>
        <ErrorBoundary label="Ontology Constraints">
          <Suspense fallback={<PanelSkeleton rows={6} />}>
            <OntologyGraph />
          </Suspense>
        </ErrorBoundary>
      </div>
    </div>
  );
}
