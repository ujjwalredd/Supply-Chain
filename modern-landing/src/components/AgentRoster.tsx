import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';

const AGENTS = [
  { name: 'orchestrator',    role: 'Routes tasks, manages agent context, decides escalation', model: 'Claude Sonnet 4.6', interval: '5 min',     color: '#0070F3' },
  { name: 'deviation_agent', role: 'Detects supplier & logistics deviations in real-time',   model: 'Claude Sonnet 4.6', interval: '15 min',    color: '#F59E0B' },
  { name: 'supplier_intel',  role: 'Researches alternate carriers & executes rerouting',      model: 'Claude Sonnet 4.6', interval: 'on-demand', color: '#10B981' },
  { name: 'dagster_guardian',role: 'Monitors pipeline health, fixes stale assets',           model: 'Rules Engine',      interval: '10 min',    color: '#8B5CF6' },
  { name: 'forecast_agent',  role: '14-day demand forecast · 91% confidence',                model: 'XGBoost + LLM',     interval: '1 day',     color: '#0070F3' },
  { name: 'ml_model_agent',  role: 'Auto-promotes models when ROC-AUC > 0.80 via MLflow',    model: 'MLflow + AutoML',   interval: '6 hr',      color: '#EC4899' },
  { name: 'inventory_agent', role: 'Triggers reorders when safety stock thresholds hit',     model: 'Claude Haiku 4.5',  interval: '30 min',    color: '#10B981' },
  { name: 'compliance_agent',role: 'Tracks tariffs, customs & trade regs across 40+ markets',model: 'Claude Sonnet 4.6', interval: '6 hr',      color: '#F59E0B' },
  { name: 'quality_agent',   role: 'Monitors defect rates, triggers quality holds auto',     model: 'Claude Haiku 4.5',  interval: '1 hr',      color: '#EF4444' },
  { name: 'carrier_agent',   role: 'Scores carriers on cost, reliability & carbon footprint',model: 'Claude Sonnet 4.6', interval: '1 day',     color: '#0070F3' },
  { name: 'finance_agent',   role: 'Tracks cost variance, flags budget anomalies',           model: 'Claude Haiku 4.5',  interval: '1 hr',      color: '#10B981' },
  { name: 'risk_agent',      role: 'Geo-political risk monitoring, route scoring',           model: 'Claude Sonnet 4.6', interval: '2 hr',      color: '#EF4444' },
  { name: 'reporting_agent', role: 'Daily digests, Slack notifications, exec summaries',     model: 'Claude Haiku 4.5',  interval: '1 day',     color: '#8B5CF6' },
];

export function AgentRoster() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <section ref={ref} className="bg-paper py-20 border-t border-black/5 overflow-hidden">
      {/* Header */}
      <div className="max-w-7xl mx-auto px-6 mb-10">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        >
          <span className="text-[10px] font-mono tracking-[0.25em] text-steel uppercase block mb-3">
            Meet the team
          </span>
          <h2 className="text-3xl md:text-4xl font-bold text-ink tracking-tight">
            13 agents.{' '}
            <span className="text-accent">Every one autonomous.</span>
          </h2>
          <p className="text-steel text-base mt-2 font-light max-w-xl">
            Each agent runs independently on its own schedule. The orchestrator coordinates — no agent waits for a human.
          </p>
        </motion.div>
      </div>

      {/* Horizontal scroll */}
      <div className="relative">
        <div className="absolute left-0 top-0 bottom-0 w-12 bg-gradient-to-r from-paper to-transparent z-10 pointer-events-none" />
        <div className="absolute right-0 top-0 bottom-0 w-12 bg-gradient-to-l from-paper to-transparent z-10 pointer-events-none" />

        <div className="flex gap-3 overflow-x-auto scrollbar-hide px-6 pb-3">
          {AGENTS.map((agent, i) => (
            <motion.div
              key={agent.name}
              initial={{ opacity: 0, y: 16 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: i * 0.04 }}
              className="flex-shrink-0 w-[230px] glass-card glass-card-hover p-4 flex flex-col gap-2.5 group"
            >
              {/* Header */}
              <div className="flex items-center justify-between">
                <div
                  className="w-2 h-2 rounded-full"
                  style={{ background: agent.color }}
                />
                <div className="flex items-center gap-1">
                  <div className="w-1 h-1 rounded-full bg-success" />
                  <span className="text-[9px] font-mono text-success">live</span>
                </div>
              </div>

              {/* Name */}
              <h3
                className="text-[12px] font-semibold font-mono tracking-tight"
                style={{ color: agent.color }}
              >
                {agent.name}
              </h3>

              {/* Role */}
              <p className="text-steel text-[11px] leading-relaxed line-clamp-2 flex-1">
                {agent.role}
              </p>

              {/* Footer */}
              <div className="flex items-center justify-between pt-2 border-t border-black/5">
                <span className="text-[9px] font-mono text-steel/70 bg-subtle px-1.5 py-0.5 rounded truncate max-w-[130px]">
                  {agent.model}
                </span>
                <span className="text-[9px] font-mono text-steel/60">↻ {agent.interval}</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Dot indicators */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={inView ? { opacity: 1 } : {}}
        transition={{ delay: 0.7 }}
        className="max-w-7xl mx-auto px-6 mt-6 flex items-center justify-between"
      >
        <div className="flex items-center gap-1.5">
          {AGENTS.map((a) => (
            <div key={a.name} className="w-1.5 h-1.5 rounded-full" style={{ background: a.color, opacity: 0.5 }} />
          ))}
        </div>
        <span className="text-[10px] font-mono text-steel/60">
          {AGENTS.length} agents · all healthy · offline=0
        </span>
      </motion.div>
    </section>
  );
}
