import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';
import { FileText, Radio, GitBranch, Cpu, Zap } from 'lucide-react';

const ease = [0.16, 1, 0.3, 1] as const;

const STAGES = [
  {
    num: '01',
    label: 'CSV / API',
    sub: 'any format',
    desc: 'Drop any file or connect a REST endpoint. Schema is inferred automatically.',
    Icon: FileText,
  },
  {
    num: '02',
    label: 'Kafka',
    sub: '12 topics · real-time',
    desc: 'Events stream to 12 typed Kafka topics for parallel real-time processing.',
    Icon: Radio,
  },
  {
    num: '03',
    label: 'Dagster',
    sub: '22 assets · medallion',
    desc: '22 data assets materialize through Bronze, Silver, and Gold lake layers.',
    Icon: GitBranch,
  },
  {
    num: '04',
    label: '13 Agents',
    sub: 'Claude Sonnet 4.6',
    desc: 'Claude + XGBoost analyze, forecast, detect deviation, and decide autonomously.',
    Icon: Cpu,
  },
  {
    num: '05',
    label: 'Decisions',
    sub: '0 human interruptions',
    desc: 'Actions execute automatically. Humans are paged only when confidence is low.',
    Icon: Zap,
  },
];

const STATS = [
  { label: 'Schema inference',     value: 'Automatic' },
  { label: 'Supported formats',    value: 'CSV, JSON, Parquet, API' },
  { label: 'Time to first insight', value: 'Under 60 seconds' },
  { label: 'Pipeline trigger',     value: 'Event-driven' },
];

export function PipelineFlow() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <section ref={ref} className="py-24 bg-paper relative z-10 border-b border-black/5 noise-texture overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 relative z-10">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8, ease }}
          className="mb-16 max-w-3xl"
        >
          <h2 className="text-sm font-mono text-accent uppercase tracking-widest mb-4 font-semibold">How Data Flows</h2>
          <h3 className="text-3xl lg:text-4xl font-semibold tracking-tight text-ink mb-6">
            Raw file in. Autonomous decision out.
          </h3>
          <p className="text-steel text-lg font-light leading-relaxed">
            Drop any CSV or connect an API. The pipeline infers schema, triggers Dagster,
            and hands off to agents in under 60 seconds.
          </p>
        </motion.div>

        {/* Stage cards — matches Capabilities style */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-x-8 gap-y-12 mb-16">
          {STAGES.map((stage, i) => {
            const Icon = stage.Icon;
            return (
              <motion.div
                key={stage.label}
                initial={{ opacity: 0, y: 20 }}
                animate={inView ? { opacity: 1, y: 0 } : {}}
                transition={{ delay: i * 0.1, duration: 0.8, ease }}
                className="flex flex-col group"
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-white/60 backdrop-blur-sm border border-white/40 shadow-sm group-hover:shadow-md group-hover:border-accent/20 group-hover:scale-110 transition-all duration-500 flex-shrink-0">
                    <Icon size={18} className="text-ink group-hover:text-accent transition-colors duration-300" />
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-[9px] font-mono text-steel/40 font-bold">{stage.num}</span>
                      <h4 className="text-ink font-semibold text-sm">{stage.label}</h4>
                    </div>
                    <span className="text-[10px] font-mono text-steel/60">{stage.sub}</span>
                  </div>
                </div>
                <p className="text-steel text-sm leading-relaxed">{stage.desc}</p>
              </motion.div>
            );
          })}
        </div>

        {/* Stats row */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: 0.8, duration: 0.5 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-6 pt-6 border-t border-black/5"
        >
          {STATS.map((s) => (
            <div key={s.label} className="flex flex-col gap-0.5">
              <span className="text-[10px] font-mono text-steel uppercase tracking-widest">{s.label}</span>
              <span className="text-sm font-semibold text-ink">{s.value}</span>
            </div>
          ))}
        </motion.div>

      </div>
    </section>
  );
}
