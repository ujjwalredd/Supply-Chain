// Improvement #2 — Live event tape
// CSS-only infinite scroll of recent agent events. Zero JS overhead.

const EVENTS = [
  { agent: 'deviation_agent', msg: 'Supplier XJ-4421 · delay +72h resolved',         time: '2m ago',  color: '#10B981' },
  { agent: 'forecast_agent',  msg: 'Demand spike +18% flagged · 14-day window',      time: '8m ago',  color: '#0070F3' },
  { agent: 'ml_model_agent',  msg: 'delay_classifier promoted · roc_auc=0.84',       time: '23m ago', color: '#0070F3' },
  { agent: 'carrier_agent',   msg: 'CN-7 performance score updated · 94/100',        time: '41m ago', color: '#10B981' },
  { agent: 'dagster_guardian',msg: 'Pipeline healthy · 0 stale assets confirmed',    time: '1h ago',  color: '#10B981' },
  { agent: 'inventory_agent', msg: 'Reorder triggered · SKU-2847 below threshold',   time: '1.4h ago',color: '#F59E0B' },
  { agent: 'risk_agent',      msg: 'Port Rotterdam congestion risk: LOW',             time: '2h ago',  color: '#10B981' },
  { agent: 'compliance_agent',msg: 'EU tariff update parsed · no action required',   time: '3h ago',  color: '#10B981' },
  { agent: 'orchestrator',    msg: 'Cycle 847 complete · 0 human escalations',       time: '5h ago',  color: '#0070F3' },
  { agent: 'quality_agent',   msg: 'Defect rate nominal · 0.3% across 4 suppliers',  time: '6h ago',  color: '#10B981' },
  { agent: 'finance_agent',   msg: 'Cost variance within threshold · +1.2%',         time: '7h ago',  color: '#0070F3' },
];

export function EventTape() {
  return (
    <div className="bg-surface border-y border-black/[0.04] py-2.5 overflow-hidden relative select-none">
      {/* Fade edges */}
      <div className="absolute left-0 inset-y-0 w-20 bg-gradient-to-r from-surface to-transparent z-10 pointer-events-none" />
      <div className="absolute right-0 inset-y-0 w-20 bg-gradient-to-l from-surface to-transparent z-10 pointer-events-none" />

      {/* Live badge */}
      <div className="absolute left-3 inset-y-0 z-20 flex items-center">
        <div className="flex items-center gap-1.5 bg-surface pr-3">
          <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
          <span className="text-[9px] font-mono font-bold text-steel uppercase tracking-widest">Live</span>
        </div>
      </div>

      {/* Scrolling tape */}
      <div className="flex w-[200%] animate-infinite-scroll hover:[animation-play-state:paused] pl-24">
        {[...EVENTS, ...EVENTS].map((ev, i) => (
          <div key={i} className="flex items-center gap-2 flex-shrink-0 px-5">
            <span className="text-[10px] font-mono font-bold" style={{ color: ev.color }}>
              {ev.agent}
            </span>
            <span className="text-[10px] font-mono text-ink/55">{ev.msg}</span>
            <span className="text-[10px] font-mono text-steel/40">{ev.time}</span>
            <span className="text-steel/20 text-base leading-none">·</span>
          </div>
        ))}
      </div>
    </div>
  );
}
