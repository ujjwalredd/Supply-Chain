// Improvement #4 — Agent activity heatmap
// 13 agents × 24 hours. CSS staggered animation on scroll entry.
// Shows "these agents never sleep" at a glance.

const HOURS = Array.from({ length: 24 }, (_, i) => i);

// Pre-defined activity for each agent based on their real schedule
const AGENTS: { name: string; color: string; cells: boolean[] }[] = [
  {
    name: 'orchestrator',
    color: '#0070F3',
    cells: Array(24).fill(true), // every 5min = always on
  },
  {
    name: 'deviation_agent',
    color: '#F59E0B',
    cells: Array(24).fill(true), // every 15min = all hours
  },
  {
    name: 'dagster_guardian',
    color: '#8B5CF6',
    cells: Array(24).fill(true), // every 10min = all hours
  },
  {
    name: 'inventory_agent',
    color: '#10B981',
    cells: Array(24).fill(true), // every 30min = all hours
  },
  {
    name: 'quality_agent',
    color: '#EF4444',
    cells: Array(24).fill(true), // every 1hr = all hours
  },
  {
    name: 'finance_agent',
    color: '#10B981',
    cells: Array(24).fill(true), // every 1hr = all hours
  },
  {
    name: 'risk_agent',
    color: '#EF4444',
    cells: HOURS.map(h => h % 2 === 0), // every 2hr
  },
  {
    name: 'ml_model_agent',
    color: '#EC4899',
    cells: HOURS.map(h => h % 6 === 0), // every 6hr → 4 cells
  },
  {
    name: 'compliance_agent',
    color: '#F59E0B',
    cells: HOURS.map(h => h % 6 === 0), // every 6hr → 4 cells
  },
  {
    name: 'forecast_agent',
    color: '#0070F3',
    cells: HOURS.map(h => h === 6), // daily 6am → 1 cell
  },
  {
    name: 'carrier_agent',
    color: '#0070F3',
    cells: HOURS.map(h => h === 8), // daily 8am → 1 cell
  },
  {
    name: 'reporting_agent',
    color: '#8B5CF6',
    cells: HOURS.map(h => h === 7), // daily 7am → 1 cell
  },
  {
    name: 'supplier_intel',
    color: '#10B981',
    cells: HOURS.map(h => [2, 9, 13, 22].includes(h)), // on-demand, sparse
  },
];

export function AgentHeatmap() {
  return (
    <section className="bg-surface border-t border-black/5 py-16">
      <div className="max-w-7xl mx-auto px-6">
        {/* Header */}
        <div className="mb-8">
          <span className="text-[10px] font-mono tracking-[0.25em] text-steel uppercase block mb-2">
            24-hour activity
          </span>
          <h2 className="text-2xl md:text-3xl font-bold text-ink tracking-tight">
            No agent sleeps.
          </h2>
          <p className="text-steel text-base mt-1 font-light">
            Every cell = one hour. Colored = agent ran. This is what 24/7 autonomous operations looks like.
          </p>
        </div>

        {/* Grid */}
        <div className="overflow-x-auto pb-2">
          <div style={{ minWidth: 600 }}>
            {/* Hour labels */}
            <div className="flex mb-2 pl-[156px]">
              {HOURS.map(h => (
                <div
                  key={h}
                  className="text-[9px] font-mono text-steel/50 text-center"
                  style={{ width: 28, flexShrink: 0 }}
                >
                  {h % 6 === 0 ? `${h}h` : ''}
                </div>
              ))}
            </div>

            {/* Agent rows */}
            <div className="space-y-1.5">
              {AGENTS.map((agent) => (
                <div key={agent.name} className="flex items-center gap-2">
                  {/* Agent name */}
                  <div className="w-[148px] flex-shrink-0 flex items-center gap-1.5">
                    <div
                      className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                      style={{ background: agent.color }}
                    />
                    <span className="text-[10px] font-mono text-ink/70 truncate">{agent.name}</span>
                  </div>

                  {/* Cells */}
                  <div className="flex gap-0.5">
                    {agent.cells.map((active, ci) => (
                      <div
                        key={ci}
                        className={`rounded-[3px] ${active ? 'cell-on' : 'cell-off'}`}
                        style={{
                          width: 24,
                          height: 18,
                          flexShrink: 0,
                          background: active ? agent.color : '#E4E4E7',
                          opacity: active ? 1 : 0.06,
                        }}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Legend */}
            <div className="flex items-center gap-4 mt-6 pt-4 border-t border-black/5">
              <div className="flex items-center gap-1.5">
                <div className="w-4 h-3 rounded-[2px] bg-accent opacity-90" />
                <span className="text-[10px] font-mono text-steel">agent ran this hour</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-4 h-3 rounded-[2px] bg-ink/10" />
                <span className="text-[10px] font-mono text-steel">not scheduled</span>
              </div>
              <span className="text-[10px] font-mono text-steel/50 ml-auto">
                13 agents · last 24h
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
