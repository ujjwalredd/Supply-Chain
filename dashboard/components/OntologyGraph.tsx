"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Constraint = {
  id: number;
  entity_id: string;
  entity_type: string;
  constraint_type: string;
  value: number;
  hard_limit: boolean;
};

export function OntologyGraph() {
  const [constraints, setConstraints] = useState<Constraint[]>([]);

  useEffect(() => {
    fetch(`${API_BASE}/ontology/constraints?limit=50`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setConstraints)
      .catch(() => setConstraints([]));
  }, []);

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      <div className="px-4 py-3 border-b border-border flex items-center justify-between">
        <p className="text-sm font-medium text-foreground">Ontology Constraints</p>
        <p className="text-xs text-mutedForeground">Brunel LogisticsDataset · injected into every AI call</p>
      </div>
      {constraints.length === 0 && (
        <p className="text-xs text-mutedForeground px-4 py-6">No constraints. Run seed script.</p>
      )}
      <div className="divide-y divide-border">
        {constraints.map((c) => (
          <div key={c.id} className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3 min-w-0">
              <span className="text-xs text-mutedForeground shrink-0">{c.entity_type}</span>
              <span className="text-sm font-medium text-foreground truncate">{c.entity_id}</span>
            </div>
            <div className="flex items-center gap-3 shrink-0 text-xs">
              <span className="text-mutedForeground">{c.constraint_type}</span>
              <span className="text-foreground tabular-nums">{c.value}</span>
              {c.hard_limit && (
                <span className="text-warning">HARD</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
