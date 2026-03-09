"use client";

import { Suspense } from "react";
import { WhatIfSimulator } from "@/components/WhatIfSimulator";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { PanelSkeleton } from "@/components/PanelSkeleton";

export default function WhatIfPage() {
  return (
    <div className="px-8 py-7 max-w-[1400px]">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">What-If Simulator</h1>
        <p className="text-sm text-mutedForeground mt-0.5">
          Model the impact of shifting volume between suppliers — cost, risk, and ontology constraint analysis via Claude
        </p>
      </div>

      <div className="max-w-3xl">
        <ErrorBoundary label="What-If Simulator">
          <Suspense fallback={<PanelSkeleton rows={6} />}>
            <WhatIfSimulator />
          </Suspense>
        </ErrorBoundary>
      </div>
    </div>
  );
}
