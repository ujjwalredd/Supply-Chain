import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';

// Real agents from agents/run_all.py — verified against codebase
const AGENTS = [
  {
    name: 'orchestrator',
    role: 'deepagents LangGraph with 3 sub-agents and 7 tools. Cross-agent root cause analysis, structured corrections via Redis pub/sub.',
    model: 'Claude Sonnet 4.6',
    interval: '5 min',
    color: '#0070F3',
    heals: 'Issues structured corrections to all agents via Redis pub/sub',
  },
  {
    name: 'kafka_guardian',
    role: 'Consumer lag, DLQ spikes, producer silence detection. Restarts containers via Docker API when thresholds breached.',
    model: 'Claude Haiku 4.5',
    interval: '30 sec',
    color: '#F59E0B',
    heals: 'Restarts Kafka containers via Docker API',
  },
  {
    name: 'dagster_guardian',
    role: 'Run failures, asset freshness, schedule health. Triggers full or incremental jobs on anomaly detection.',
    model: 'Claude Haiku 4.5',
    interval: '2 min',
    color: '#8B5CF6',
    heals: 'Triggers medallion_full_pipeline or incremental job',
  },
  {
    name: 'bronze_agent',
    role: 'Parquet existence, schema drift, freshness validation on raw Bronze layer. Triggers Dagster materialization on failure.',
    model: 'Claude Haiku 4.5',
    interval: '5 min',
    color: '#71717A',
    heals: 'Triggers Dagster asset materialization',
  },
  {
    name: 'silver_agent',
    role: 'Null rates, dedup verification, status enum validation, delay range checks across the validated Silver layer.',
    model: 'Claude Haiku 4.5',
    interval: '5 min',
    color: '#10B981',
    heals: 'Escalates to medallion_supervisor on repeated failure',
  },
  {
    name: 'gold_agent',
    role: 'Financial formula re-validation, ML output bounds, forecast sanity checks on the AI-ready Gold layer.',
    model: 'Claude Haiku 4.5',
    interval: '10 min',
    color: '#F59E0B',
    heals: 'Escalates to medallion_supervisor',
  },
  {
    name: 'medallion_supervisor',
    role: 'Data contract enforcement across the Bronze → Silver → Gold dependency chain. Ensures ordering and freshness.',
    model: 'Claude Haiku 4.5',
    interval: '3 min',
    color: '#EC4899',
    heals: 'Publishes cross-layer correction alerts',
  },
  {
    name: 'ai_quality_monitor',
    role: 'Stuck pending actions, low-confidence re-triggers, REROUTE validation. Guards AI output quality on every cycle.',
    model: 'Claude Haiku 4.5',
    interval: '60 sec',
    color: '#EF4444',
    heals: 'Re-triggers low-confidence actions automatically',
  },
  {
    name: 'database_health',
    role: 'Connection count, long queries, lock detection, table sizes across the PostgreSQL supply chain database.',
    model: 'Claude Haiku 4.5',
    interval: '60 sec',
    color: '#0070F3',
    heals: 'Alerts on long-running locks and pool exhaustion',
  },
  {
    name: 'data_ingestion_agent',
    role: 'Watches /data/source/. deepagents iterative loop: read_csv_sample → generate loader → validate → fix (up to 3 attempts).',
    model: 'Claude Haiku 4.5',
    interval: '60 sec',
    color: '#10B981',
    heals: 'Auto-retries loader generation up to 3 times',
  },
  {
    name: 'mlflow_guardian',
    role: 'Monitors roc_auc drift. Hard floors: never promotes if roc_auc < 0.60 or train_rows < 100. Triggers retraining on drift.',
    model: 'Claude Haiku 4.5',
    interval: '5 min',
    color: '#EC4899',
    heals: 'Resets cooldown and triggers real MLflow retraining',
  },
  {
    name: 'feature_engineer',
    role: 'Reads Gold layer, asks Claude for 5 new features, validates each via 5-gate sandbox, writes to computed_features/.',
    model: 'Claude Haiku 4.5',
    interval: '15 min',
    color: '#8B5CF6',
    heals: 'Triggers incremental ML retraining after feature write',
  },
  {
    name: 'dashboard_agent',
    role: 'Reads agent heartbeats + Gold metrics. Asks Claude for panel spec. Builds deterministic Grafana JSON. Pushes via API.',
    model: 'Claude Haiku 4.5',
    interval: '10 min',
    color: '#0070F3',
    heals: 'Auto-regenerates and pushes broken Grafana panels',
  },
];

export function AgentRoster() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <section ref={ref} className="bg-paper py-20 border-t border-black/5 overflow-hidden">
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
            Each agent runs independently on its own schedule, self-heals on failure, and escalates only when genuinely needed.
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
              className="flex-shrink-0 w-[250px] glass-card glass-card-hover p-4 flex flex-col gap-2.5 group"
            >
              <div className="flex items-center justify-between">
                <div className="w-2 h-2 rounded-full" style={{ background: agent.color }} />
                <div className="flex items-center gap-1">
                  <div className="w-1 h-1 rounded-full bg-success" />
                  <span className="text-[9px] font-mono text-success">live</span>
                </div>
              </div>

              <h3 className="text-[12px] font-semibold font-mono tracking-tight" style={{ color: agent.color }}>
                {agent.name}
              </h3>

              <p className="text-steel text-[11px] leading-relaxed line-clamp-2 flex-1">
                {agent.role}
              </p>

              {/* Self-heal line */}
              <div className="text-[10px] text-ink/50 font-mono bg-black/[0.03] rounded px-2 py-1 leading-snug">
                ↺ {agent.heals}
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-black/5">
                <span className="text-[9px] font-mono text-steel/70 bg-subtle px-1.5 py-0.5 rounded truncate max-w-[140px]">
                  {agent.model}
                </span>
                <span className="text-[9px] font-mono text-steel/60">↻ {agent.interval}</span>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

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
