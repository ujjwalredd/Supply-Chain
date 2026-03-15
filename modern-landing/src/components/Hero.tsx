import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Github, ArrowRight } from 'lucide-react';

const ease = [0.16, 1, 0.3, 1] as const;

function AnimatedHeadline() {
  return (
    <h1 className="text-5xl sm:text-6xl md:text-[72px] font-bold tracking-tighter leading-[1.05] mb-6 text-ink">
      <motion.span
        className="block"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease, delay: 0.1 }}
      >
        Your supply chain
      </motion.span>
      <motion.span
        className="block"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease, delay: 0.22 }}
      >
        runs{' '}
        <span className="text-accent">itself.</span>
      </motion.span>
    </h1>
  );
}

function MetricCard({ label, value, sub, delay }: { label: string; value: string; sub: string; delay: number }) {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setShow(true), delay * 1000 + 700);
    return () => clearTimeout(t);
  }, [delay]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease, delay: 0.5 + delay }}
      className="liquid-glass rounded-xl px-5 py-4 flex flex-col gap-1 min-w-[108px]"
    >
      <span className="text-[10px] font-mono uppercase tracking-widest text-steel">{label}</span>
      <span className="text-2xl font-bold text-ink tracking-tight">{show ? value : '—'}</span>
      <span className="text-[10px] text-steel font-mono">{sub}</span>
    </motion.div>
  );
}

const LOG_LINES = [
  { prefix: 'orchestrator',    msg: 'analyzing 847 data points across 13 agents...', color: 'text-accent' },
  { prefix: 'deviation_agent', msg: 'ALERT: Supplier XJ-4421 delay +72h detected',   color: 'text-warning' },
  { prefix: 'supplier_intel',  msg: 'fetching alternate carrier options...',          color: 'text-steel' },
  { prefix: 'supplier_intel',  msg: 'Alt carrier CN-7 available · ETA delta: +6h',   color: 'text-success' },
  { prefix: 'orchestrator',    msg: 'issuing correction to supplier_intel reroute',   color: 'text-accent' },
  { prefix: 'dagster_guardian',msg: 'pipeline healthy · 0 stale assets',             color: 'text-success' },
  { prefix: 'forecast_agent',  msg: 'demand spike +18% next 14d · confidence 91%',   color: 'text-steel' },
  { prefix: 'ml_model_agent',  msg: 'delay_classifier roc_auc=0.84 · promoting...',  color: 'text-accent' },
  { prefix: 'deviation_agent', msg: 'RESOLVED — no human intervention required',      color: 'text-success' },
  { prefix: 'orchestrator',    msg: 'all agents healthy · offline=0 · cycle complete', color: 'text-accent' },
];

function AgentTerminal() {
  const [phase, setPhase] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (phase < LOG_LINES.length) {
      const t = setTimeout(() => {
        setPhase(p => p + 1);
        containerRef.current?.scrollTo({ top: containerRef.current.scrollHeight });
      }, 900);
      return () => clearTimeout(t);
    } else {
      const t = setTimeout(() => setPhase(0), 3500);
      return () => clearTimeout(t);
    }
  }, [phase]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.9, ease, delay: 0.35 }}
      className="relative w-full"
    >
      <div className="liquid-glass rounded-2xl overflow-hidden shadow-card">
        {/* Chrome bar */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-black/5 bg-surface/80">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-400/80" />
            <div className="w-3 h-3 rounded-full bg-amber-400/80" />
            <div className="w-3 h-3 rounded-full bg-emerald-400/80" />
          </div>
          <span className="ml-3 text-[11px] font-mono text-steel">agent_activity.log</span>
          <div className="ml-auto flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
            <span className="text-[10px] font-mono text-success">LIVE</span>
          </div>
        </div>

        {/* Log output */}
        <div
          ref={containerRef}
          className="p-5 h-64 overflow-y-auto scrollbar-hide bg-[#FAFAFA] font-mono text-[11px] leading-relaxed space-y-2"
        >
          {LOG_LINES.slice(0, phase).map((line, idx) => (
            <motion.div
              key={`${idx}-${phase}`}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
              className="flex items-start gap-2"
            >
              <span className="text-steel/40 select-none flex-shrink-0">›</span>
              <span className={`flex-shrink-0 font-semibold ${line.color}`}>{line.prefix}</span>
              <span className="text-steel/50">·</span>
              <span className="text-ink/65">{line.msg}</span>
            </motion.div>
          ))}
          <div className="flex items-center gap-2 h-4">
            <span className="text-steel/40">›</span>
            <motion.span
              animate={{ opacity: [1, 0, 1] }}
              transition={{ repeat: Infinity, duration: 1.1 }}
              className="w-2 h-3.5 bg-accent inline-block rounded-sm"
            />
          </div>
        </div>

        <div className="px-5 py-2.5 border-t border-black/5 bg-surface/60 flex items-center justify-between text-[10px] font-mono text-steel">
          <span>13 agents · cycle 300s</span>
          <span className="text-success font-semibold">offline=0</span>
        </div>
      </div>
    </motion.div>
  );
}

const TECH_STACK = [
  'Kafka', 'PostgreSQL', 'Redis', 'Dagster', 'FastAPI',
  'MinIO', 'Claude Sonnet', 'ksqlDB', 'XGBoost', 'MLflow',
  'Prometheus', 'Grafana', 'deepagents', 'OpenTelemetry',
];

export function Hero() {
  return (
    <section className="relative min-h-screen pt-28 pb-16 md:pt-36 md:pb-24 overflow-hidden bg-paper">
      {/* Background layers */}
      <div className="absolute inset-0 pointer-events-none">
        {/* Dot grid — pure CSS, zero JS */}
        <div className="dot-grid-bg absolute inset-0" />
        {/* Radial fade overlay so dots fade out at bottom */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_0%,rgba(0,112,243,0.05),transparent_55%)]" />
        <div className="absolute bottom-0 inset-x-0 h-40 bg-gradient-to-t from-paper to-transparent" />
      </div>

      <div className="max-w-7xl mx-auto px-6 relative z-10">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 xl:gap-20 items-center min-h-[calc(100vh-200px)]">

          {/* LEFT */}
          <div className="flex flex-col justify-center">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, ease }}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-black/8 bg-white/80 backdrop-blur shadow-sm mb-8 w-fit"
            >
              <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
              <span className="text-[10px] font-mono tracking-widest text-steel uppercase">
                13 Agents · 0 Human Interventions · AGPL-3.0
              </span>
            </motion.div>

            <AnimatedHeadline />

            <motion.p
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, ease, delay: 0.35 }}
              className="text-steel text-lg md:text-xl font-light leading-relaxed mb-10 max-w-lg"
            >
              13 AI agents monitor, predict, and self-heal your supply chain 24/7.
              Detect disruptions{' '}
              <span className="text-ink font-medium">4+ hours early.</span>{' '}
              Drop a CSV — pipeline runs in{' '}
              <span className="text-ink font-medium">60 seconds.</span>
            </motion.p>

            <div className="flex flex-wrap gap-3 mb-10">
              <MetricCard label="Agents"        value="13"    sub="running 24/7"   delay={0}   />
              <MetricCard label="Interventions" value="0"     sub="human required" delay={0.08} />
              <MetricCard label="Early warning" value="4.2h"  sub="avg lead time"  delay={0.16} />
              <MetricCard label="CSV → Pipeline" value="<60s" sub="automated"      delay={0.24} />
            </div>

            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, ease, delay: 0.55 }}
              className="flex flex-col sm:flex-row items-start gap-3"
            >
              <a
                href="#design-partner"
                className="group flex items-center gap-2 bg-ink text-paper px-6 py-3 rounded-xl font-semibold text-sm hover:bg-black transition-colors shadow-md hover:shadow-lg"
              >
                Apply for Design Partner Access
                <ArrowRight size={15} className="group-hover:translate-x-0.5 transition-transform" />
              </a>
              <a
                href="https://github.com/ujjwalredd/Supply-Chain"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 border border-black/10 text-ink px-6 py-3 rounded-xl font-semibold text-sm hover:bg-subtle hover:border-black/15 transition-colors shadow-sm"
              >
                <Github size={16} /> View on GitHub
              </a>
            </motion.div>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.6, delay: 0.75 }}
              className="mt-3 text-[11px] font-mono text-steel/60"
            >
              Limited spots · Free for 90 days · No credit card
            </motion.p>
          </div>

          {/* RIGHT — terminal */}
          <div className="hidden lg:flex flex-col justify-center">
            <AgentTerminal />
          </div>
        </div>

        {/* Tech ticker */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.9 }}
          className="mt-8 w-full overflow-hidden relative"
        >
          <div className="text-[10px] font-mono font-medium text-steel/50 uppercase tracking-widest mb-5 text-center">
            Built on an enterprise-grade open source stack
          </div>
          <div className="absolute left-0 top-6 bottom-0 w-24 bg-gradient-to-r from-paper to-transparent z-10 pointer-events-none" />
          <div className="absolute right-0 top-6 bottom-0 w-24 bg-gradient-to-l from-paper to-transparent z-10 pointer-events-none" />
          <div className="flex w-[200%] animate-infinite-scroll hover:[animation-play-state:paused]">
            {[0, 1].map(copy => (
              <div key={copy} className="flex w-1/2 justify-around items-center min-w-max gap-12 sm:gap-16 px-6">
                {TECH_STACK.map((tech) => (
                  <span key={tech} className="text-lg sm:text-xl font-bold tracking-tight text-ink/12 hover:text-ink/40 transition-colors duration-200 whitespace-nowrap">
                    {tech}
                  </span>
                ))}
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  );
}
