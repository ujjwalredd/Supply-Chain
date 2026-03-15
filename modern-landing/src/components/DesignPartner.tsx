import { useState } from 'react';
import { motion } from 'framer-motion';
import { Check } from 'lucide-react';

const smoothTransition = { duration: 0.8, ease: [0.16, 1, 0.3, 1] as any };

const perks = [
  'Full system deployed on your infrastructure',
  'All 13 agents configured for your data',
  'Direct line to the founding team',
  'Permanent discount when paid plans launch',
  'Co-author the product roadmap',
];

export function DesignPartner() {
  const [form, setForm] = useState({ name: '', company: '', email: '', problem: '' });
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <section id="design-partner" className="py-24 border-b border-black/5 bg-surface noise-texture relative overflow-hidden">
      {/* Ambient glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] bg-hero-glow pointer-events-none opacity-50" />

      <div className="max-w-5xl mx-auto px-6 relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={smoothTransition}
          className="text-center mb-14"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-black/10 bg-white/60 backdrop-blur-lg shadow-sm mb-6">
            <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            <span className="text-[10px] font-mono tracking-widest text-steel uppercase">Limited Access — 5 Spots</span>
          </div>
          <h2 className="text-4xl lg:text-5xl font-semibold tracking-tight text-ink mb-4">
            Be one of 5 companies<br />that shapes this.
          </h2>
          <p className="text-steel text-lg font-light max-w-2xl mx-auto leading-relaxed">
            We're looking for supply chain operators who want a production-grade AI OS — not a demo.
            You get full access free for 90 days. We get real-world feedback. You become a case study.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
          {/* Left: Perks */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: '-50px' }}
            transition={smoothTransition}
          >
            <h3 className="text-ink font-semibold mb-6">What you get</h3>
            <div className="space-y-4">
              {perks.map((perk, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.08, ...smoothTransition }}
                  className="flex items-start gap-3"
                >
                  <div className="w-5 h-5 rounded-full bg-success/10 border border-success/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Check size={11} className="text-success" />
                  </div>
                  <span className="text-ink text-sm leading-relaxed">{perk}</span>
                </motion.div>
              ))}
            </div>

            {/* Spots counter */}
            <div className="mt-10">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono text-steel uppercase tracking-widest">Spots taken</span>
                <span className="text-xs font-mono text-ink font-semibold">2 / 5</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-black/5 overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  whileInView={{ width: '40%' }}
                  viewport={{ once: true }}
                  transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
                  className="h-full bg-accent rounded-full"
                />
              </div>
              <p className="text-[11px] font-mono text-steel mt-2">3 spots remaining · Free for 90 days · No credit card</p>
            </div>
          </motion.div>

          {/* Right: Form */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: '-50px' }}
            transition={smoothTransition}
          >
            {submitted ? (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="liquid-glass rounded-2xl p-8 text-center"
              >
                <div className="w-12 h-12 rounded-full bg-success/10 border border-success/30 flex items-center justify-center mx-auto mb-4">
                  <Check size={20} className="text-success" />
                </div>
                <h4 className="text-ink font-semibold text-lg mb-2">Application received</h4>
                <p className="text-steel text-sm leading-relaxed">
                  We review every application personally.<br />
                  You'll hear back within 48 hours.
                </p>
              </motion.div>
            ) : (
              <form onSubmit={handleSubmit} className="liquid-glass rounded-2xl p-8 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-[11px] font-mono text-steel uppercase tracking-widest mb-1.5 block">Name</label>
                    <input
                      required
                      value={form.name}
                      onChange={e => setForm({ ...form, name: e.target.value })}
                      className="w-full px-3 py-2.5 rounded-lg border border-black/8 bg-white/60 text-ink text-sm focus:outline-none focus:border-accent/40 transition-colors placeholder:text-steel/50"
                      placeholder="Your name"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-mono text-steel uppercase tracking-widest mb-1.5 block">Company</label>
                    <input
                      required
                      value={form.company}
                      onChange={e => setForm({ ...form, company: e.target.value })}
                      className="w-full px-3 py-2.5 rounded-lg border border-black/8 bg-white/60 text-ink text-sm focus:outline-none focus:border-accent/40 transition-colors placeholder:text-steel/50"
                      placeholder="Company name"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-[11px] font-mono text-steel uppercase tracking-widest mb-1.5 block">Email</label>
                  <input
                    required
                    type="email"
                    value={form.email}
                    onChange={e => setForm({ ...form, email: e.target.value })}
                    className="w-full px-3 py-2.5 rounded-lg border border-black/8 bg-white/60 text-ink text-sm focus:outline-none focus:border-accent/40 transition-colors placeholder:text-steel/50"
                    placeholder="you@company.com"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-mono text-steel uppercase tracking-widest mb-1.5 block">Biggest supply chain problem?</label>
                  <textarea
                    required
                    rows={3}
                    value={form.problem}
                    onChange={e => setForm({ ...form, problem: e.target.value })}
                    className="w-full px-3 py-2.5 rounded-lg border border-black/8 bg-white/60 text-ink text-sm focus:outline-none focus:border-accent/40 transition-colors resize-none placeholder:text-steel/50"
                    placeholder="e.g. We can't see disruptions until they've already hit us..."
                  />
                </div>
                <button
                  type="submit"
                  className="w-full bg-ink text-paper py-3 rounded-lg font-semibold text-sm hover:bg-black transition-colors shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-transform"
                >
                  Apply for Design Partner Access →
                </button>
                <p className="text-[11px] text-steel text-center font-mono">
                  We review every application personally · Response within 48 hours
                </p>
              </form>
            )}
          </motion.div>
        </div>
      </div>
    </section>
  );
}
