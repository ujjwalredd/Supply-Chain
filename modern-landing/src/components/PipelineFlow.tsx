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
    color: '#71717A',
    border: '#E4E4E7',
    bg: '#FAFAFA',
  },
  {
    num: '02',
    label: 'Kafka',
    sub: '12 topics · real-time',
    desc: 'Events stream to 12 typed Kafka topics for parallel real-time processing.',
    Icon: Radio,
    color: '#0070F3',
    border: '#BFDBFE',
    bg: '#EFF6FF',
  },
  {
    num: '03',
    label: 'Dagster',
    sub: '22 assets · medallion',
    desc: '22 data assets materialize through Bronze, Silver, and Gold lake layers.',
    Icon: GitBranch,
    color: '#8B5CF6',
    border: '#DDD6FE',
    bg: '#F5F3FF',
  },
  {
    num: '04',
    label: '13 Agents',
    sub: 'Claude Sonnet 4.6',
    desc: 'Claude + XGBoost analyze, forecast, detect deviation, and decide autonomously.',
    Icon: Cpu,
    color: '#0070F3',
    border: '#BFDBFE',
    bg: '#EFF6FF',
  },
  {
    num: '05',
    label: 'Decisions',
    sub: '0 human interruptions',
    desc: 'Actions execute automatically. Humans are paged only when confidence is low.',
    Icon: Zap,
    color: '#10B981',
    border: '#A7F3D0',
    bg: '#F0FDF9',
  },
];

const STATS = [
  { label: 'Schema inference',      value: 'Automatic' },
  { label: 'Supported formats',     value: 'CSV, JSON, Parquet, API' },
  { label: 'Time to first insight',  value: 'Under 60 seconds' },
  { label: 'Pipeline trigger',      value: 'Event-driven' },
];

export function PipelineFlow() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <section ref={ref} className="bg-paper py-16 border-t border-black/5">
      <div className="max-w-6xl mx-auto px-6">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, ease }}
          className="mb-12"
        >
          <span className="text-[10px] font-mono tracking-[0.25em] text-steel uppercase block mb-2">
            How data flows
          </span>
          <h2 className="text-2xl md:text-3xl font-bold text-ink tracking-tight">
            Raw file in. Autonomous decision out.
          </h2>
          <p className="text-steel text-base mt-1.5 font-light max-w-xl">
            Drop any CSV or connect an API. The pipeline infers schema, triggers Dagster,
            and hands off to agents in under 60 seconds.
          </p>
        </motion.div>

        {/* Pipeline */}
        <div className="overflow-x-auto pb-4">
          <div className="relative" style={{ minWidth: 700 }}>

            {/* Stage cards row */}
            <div className="flex items-stretch gap-0">

              {/* Gradient connector line — sits at icon center (top: 16px padding + 20px = 36px) */}
              <div
                className="absolute z-0 pointer-events-none"
                style={{
                  top: 36,
                  left: 'calc(10% + 2px)',
                  right: 'calc(10% + 2px)',
                  height: 2,
                  background:
                    'linear-gradient(to right, #E4E4E7 0%, #BFDBFE 25%, #DDD6FE 50%, #BFDBFE 75%, #A7F3D0 100%)',
                }}
              />

              {/* Animated packets — 3 staggered for continuous flow */}
              {inView && (
                <div
                  className="absolute z-10 pointer-events-none"
                  style={{
                    top: 31,
                    left: 'calc(10% + 2px)',
                    right: 'calc(10% + 2px)',
                    height: 10,
                  }}
                >
                  {[0, 1.07, 2.13].map((d) => (
                    <div key={d} className="pipeline-packet" style={{ animationDelay: `${d}s` }} />
                  ))}
                </div>
              )}

              {/* Stage cards */}
              {STAGES.map((stage, i) => (
                <motion.div
                  key={stage.label}
                  initial={{ opacity: 0, y: 20 }}
                  animate={inView ? { opacity: 1, y: 0 } : {}}
                  transition={{ duration: 0.55, ease, delay: i * 0.1 }}
                  className="relative z-10 flex flex-col rounded-2xl border p-4 shadow-sm"
                  style={{
                    width: '19%',
                    marginLeft: i === 0 ? 0 : '1.25%',
                    background: stage.bg,
                    borderColor: stage.border,
                    borderTopWidth: 2,
                    borderTopColor: stage.color,
                  }}
                >
                  {/* Top row: icon + step number */}
                  <div className="flex items-center justify-between mb-3">
                    <div
                      className="w-10 h-10 rounded-xl flex items-center justify-center"
                      style={{ background: `${stage.color}18` }}
                    >
                      <stage.Icon size={18} color={stage.color} />
                    </div>
                    <span className="text-[10px] font-mono text-steel/35 font-bold">{stage.num}</span>
                  </div>

                  {/* Title */}
                  <span
                    className="text-sm font-bold leading-tight block"
                    style={{ color: stage.color === '#71717A' ? '#09090B' : stage.color }}
                  >
                    {stage.label}
                  </span>

                  {/* Sub */}
                  <span className="text-[10px] font-mono text-steel mt-0.5 block">{stage.sub}</span>

                  {/* Desc */}
                  <p className="text-[11px] text-steel/70 leading-snug mt-2 flex-1">{stage.desc}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </div>

        {/* Stats row */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: 0.8, duration: 0.5 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-8 pt-6 border-t border-black/5"
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
