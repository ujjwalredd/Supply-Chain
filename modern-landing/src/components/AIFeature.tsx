import { motion } from 'framer-motion';
import { ArrowRight, BrainCircuit, ActivitySquare } from 'lucide-react';

export function AIFeature() {
  const ontologyRules = [
    { name: 'Claude Sonnet Primary', desc: 'Evaluates deviations against strict mathematical bounds.', status: 'Active' },
    { name: 'Execution Quality Scoring', desc: 'Deterministically scores generated schemas (0.0 to 1.0).', status: 'Active' },
    { name: 'GPT-4o Zero-Downtime Fallback', desc: 'Automatic reroute if reasoning quality score drops < 0.4.', status: 'Strict' },
  ];

  return (
    <section id="platform" className="py-24 border-b border-black/5 bg-paper relative overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

        {/* Left Concept */}
        <div>
          <h2 className="text-3xl lg:text-5xl font-semibold tracking-tight text-ink mb-6">
            Multi-Model AI Pipeline.
          </h2>
          <p className="text-steel text-lg font-light leading-relaxed mb-8">
            No hallucinated logistics. We use a deterministic quality scoring engine. Claude Sonnet evaluates every deviation, but if the execution schema quality drops below a 0.4 threshold, the reasoning engine automatically fails over to GPT-4o.
          </p>

          <div className="space-y-4">
            {ontologyRules.map((rule, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ delay: idx * 0.1, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="flex items-center justify-between p-4 rounded-xl border border-black/5 bg-surface glass-card-hover group cursor-pointer"
              >
                <div>
                  <h4 className="text-ink font-semibold text-sm group-hover:text-accent transition-colors">{rule.name}</h4>
                  <p className="text-steel text-xs mt-1">{rule.desc}</p>
                </div>
                <div className="text-[10px] font-mono tracking-widest text-accent bg-accent/10 px-2 py-1 rounded font-semibold border border-accent/20">
                  {rule.status}
                </div>
              </motion.div>
            ))}
          </div>

          <a
            href="https://github.com/ujjwalredd/Supply-Chain/tree/main/reasoning"
            target="_blank"
            rel="noopener noreferrer"
            className="mt-8 inline-flex items-center gap-2 text-sm text-ink font-medium hover:text-accent transition-colors"
          >
            View Full Rule Engine <ArrowRight size={16} />
          </a>
        </div>

        {/* Right Code Block Vis */}
        <motion.div
          initial={{ opacity: 0, y: 40, scale: 0.98 }}
          whileInView={{ opacity: 1, y: 0, scale: 1 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
          className="relative lg:ml-8"
        >
          {/* Subtle Glow Behind Block */}
          <div className="absolute inset-0 bg-accent/5 blur-[100px] rounded-full pointer-events-none" />

          <div className="glass-card rounded-[20px] bg-white border border-black/10 overflow-hidden relative z-10 shadow-2xl">
            {/* Mac OS style window header */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-black/5 bg-surface">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-400" />
                <div className="w-3 h-3 rounded-full bg-amber-400" />
                <div className="w-3 h-3 rounded-full bg-emerald-400" />
              </div>
              <div className="ml-4 text-[10px] font-mono font-medium text-steel">analysis_result.json</div>
            </div>

            <div className="p-6 font-mono text-xs sm:text-sm text-steel leading-relaxed overflow-x-auto bg-[#FAFAFA]">
              <span className="text-ink">{'{'}</span><br />
              <span className="ml-4 text-ink font-semibold">"deviation_id"</span>: <span className="text-accent">"DEV-092A"</span>,<br />
              <span className="ml-4 text-ink font-semibold">"root_cause_analysis"</span>: <span className="text-ink">{'{'}</span><br />
              <span className="ml-8 text-ink font-semibold">"primary_factor"</span>: <span className="text-accent">"Vessel congested"</span>,<br />
              <span className="ml-8 text-ink font-semibold">"confidence_score"</span>: <span className="text-success">0.982</span><br />
              <span className="ml-4 text-ink">{'}'}</span>,<br />
              <span className="ml-4 text-ink font-semibold">"financial_impact"</span>: <span className="text-ink">{'{'}</span><br />
              <span className="ml-8 text-ink font-semibold">"computed_loss_usd"</span>: <span className="text-warning">2400000</span>,<br />
              <span className="ml-8 text-ink font-semibold">"penalty_risk"</span>: <span className="text-danger">"CRITICAL"</span><br />
              <span className="ml-4 text-ink">{'}'}</span>,<br />
              <span className="ml-4 text-ink font-semibold">"model_used"</span>: <span className="text-accent">"claude-sonnet-3.5"</span>,<br />
              <span className="ml-4 text-ink font-semibold">"quality_score"</span>: <span className="text-success">0.82</span>,<br />
              <span className="ml-4 text-ink font-semibold">"fallback_triggered"</span>: <span className="text-warning">false</span>,<br />
              <span className="ml-4 text-ink font-semibold">"action_executor"</span>: <span className="text-accent">"REROUTE"</span><br />
              <span className="text-ink">{'}'}</span>
            </div>
          </div>

          {/* Floating UI Badges */}
          <motion.div
            animate={{ y: [0, -10, 0] }} transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
            className="absolute -bottom-6 -right-6 flex items-center justify-center w-16 h-16 rounded-2xl bg-white border border-black/5 shadow-xl z-20"
          >
            <ActivitySquare className="text-accent" size={24} />
          </motion.div>
          <motion.div
            animate={{ y: [0, 8, 0] }} transition={{ repeat: Infinity, duration: 5, ease: "easeInOut", delay: 1 }}
            className="absolute -top-6 -left-6 flex items-center justify-center w-12 h-12 rounded-xl bg-white border border-black/5 shadow-xl z-20"
          >
            <BrainCircuit className="text-ink" size={20} />
          </motion.div>

        </motion.div>
      </div>
    </section>
  );
}
