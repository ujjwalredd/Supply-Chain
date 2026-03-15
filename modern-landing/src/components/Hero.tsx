import { motion } from 'framer-motion';
import { Github } from 'lucide-react';
import { MagneticButton } from './MagneticButton';

const smoothTransition = { duration: 1, ease: [0.16, 1, 0.3, 1] as any };

export function Hero() {
  return (
    <section className="relative pt-32 pb-20 md:pt-48 md:pb-32 overflow-hidden noise-texture">
      {/* Soft Ambient Glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-hero-glow pointer-events-none" />

      {/* Very faint background grid */}
      <div className="absolute inset-0 bg-subtle-grid pointer-events-none [background-size:24px_24px] [mask-image:linear-gradient(to_bottom,white,transparent)]" />

      <div className="max-w-7xl mx-auto px-6 flex flex-col items-center text-center relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 15, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ ...smoothTransition, delay: 0 }}
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/40 bg-white/60 backdrop-blur-lg shadow-sm mb-8"
        >
          <div className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
          <span className="text-[10px] font-mono tracking-widest text-steel uppercase text-ink">13 Agents Running · 0 Human Interventions · AGPL-3.0</span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...smoothTransition, delay: 0.1 }}
          className="text-5xl md:text-[80px] font-semibold tracking-tighter text-gradient mb-8 leading-[1.05] max-w-4xl"
        >
          Your supply chain<br />runs itself.
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...smoothTransition, delay: 0.2 }}
          className="text-steel text-lg md:text-xl max-w-2xl font-light leading-relaxed mb-6"
        >
          13 AI agents monitor, predict, and self-heal your entire supply chain 24/7.
          Detect disruptions 4+ hours before they become crises. No dashboards to watch. No alerts to triage.
        </motion.p>

        {/* Live Metrics Row */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...smoothTransition, delay: 0.25 }}
          className="flex flex-wrap items-center justify-center gap-6 mb-10 font-mono text-xs text-steel"
        >
          {[
            { label: '13', sub: 'Agents Running' },
            { label: '0', sub: 'Human Interventions' },
            { label: '4.2h', sub: 'Avg Early Warning' },
            { label: '<60s', sub: 'CSV → Pipeline' },
          ].map((m) => (
            <div key={m.sub} className="flex flex-col items-center gap-0.5">
              <span className="text-ink font-semibold text-base">{m.label}</span>
              <span className="text-[10px] uppercase tracking-widest">{m.sub}</span>
            </div>
          ))}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ ...smoothTransition, delay: 0.3 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          <MagneticButton
            href="#design-partner"
            className="flex items-center justify-center gap-2 bg-ink text-paper px-6 py-3 rounded-lg font-medium hover:bg-black transition-all duration-300 min-w-[220px] shadow-md hover:shadow-lg hover:-translate-y-0.5"
          >
            Apply for Design Partner Access
          </MagneticButton>
          <MagneticButton
            href="https://github.com/ujjwalredd/Supply-Chain"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 border border-black/10 text-ink px-6 py-3 rounded-lg font-medium hover:bg-subtle transition-all duration-300 min-w-[180px] shadow-sm hover:-translate-y-0.5"
          >
            <Github size={18} /> View on GitHub
          </MagneticButton>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ ...smoothTransition, delay: 0.4 }}
          className="mt-3 text-[11px] font-mono text-steel"
        >
          5 spots remaining · Free for 90 days · No credit card
        </motion.p>

        {/* Integration Ticker */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 0.6 }}
          className="mt-20 md:mt-32 w-full max-w-5xl mx-auto overflow-hidden relative"
        >
          <div className="text-[10px] font-mono font-medium text-steel uppercase tracking-widest mb-6">
            Built on an enterprise-grade open source stack
          </div>

          {/* Gradients for fading effect on edges */}
          <div className="absolute left-0 top-10 bottom-0 w-24 bg-gradient-to-r from-paper to-transparent z-10" />
          <div className="absolute right-0 top-10 bottom-0 w-24 bg-gradient-to-l from-paper to-transparent z-10" />

          <div className="flex w-[200%] animate-infinite-scroll hover:[animation-play-state:paused] cursor-default">
            {/* First Set */}
            <div className="flex w-1/2 justify-around items-center min-w-max gap-12 sm:gap-20 px-6">
              {['Kafka', 'PostgreSQL', 'Redis', 'Dagster', 'FastAPI', 'MinIO', 'Claude Sonnet', 'ksqlDB', 'XGBoost', 'MLflow', 'Prometheus', 'Grafana'].map((tech) => (
                <span key={tech} className="text-xl sm:text-2xl font-bold tracking-tight text-ink/20 hover:text-ink/60 transition-colors duration-300">
                  {tech}
                </span>
              ))}
            </div>
            {/* Duplicate Set for smooth infinite loop */}
            <div className="flex w-1/2 justify-around items-center min-w-max gap-12 sm:gap-20 px-6">
              {['Kafka', 'PostgreSQL', 'Redis', 'Dagster', 'FastAPI', 'MinIO', 'Claude Sonnet', 'ksqlDB', 'XGBoost', 'MLflow', 'Prometheus', 'Grafana'].map((tech) => (
                <span key={`dup-${tech}`} className="text-xl sm:text-2xl font-bold tracking-tight text-ink/20 hover:text-ink/60 transition-colors duration-300">
                  {tech}
                </span>
              ))}
            </div>
          </div>
        </motion.div>

      </div>
    </section>
  );
}
