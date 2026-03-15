import { useState } from 'react';
import { motion } from 'framer-motion';
import { Check, Loader2 } from 'lucide-react';

// ─── FORM ENDPOINT ────────────────────────────────────────────
// Option A — Formspree (recommended, free):
//   1. Sign up at https://formspree.io
//   2. Create a new form, copy the form ID (e.g. "xabc1234")
//   3. Replace "YOUR_FORMSPREE_ID" below with your actual ID
//
// Option B — Resend (see /api/contact.ts for the serverless fn):
//   Set FORM_ENDPOINT to "/api/contact"
// ──────────────────────────────────────────────────────────────
const FORM_ENDPOINT = 'https://formspree.io/f/xreyaval';

const perks = [
  'Full system deployed on your infrastructure',
  'All 13 agents configured for your data',
  'Direct line to the founding team',
  'Permanent discount when paid plans launch',
  'Co-author the product roadmap',
];

type Status = 'idle' | 'submitting' | 'success' | 'error';

export function DesignPartner() {
  const [form, setForm] = useState({ name: '', company: '', email: '', problem: '' });
  const [status, setStatus] = useState<Status>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('submitting');
    setErrorMsg('');

    try {
      const res = await fetch(FORM_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify(form),
      });

      if (res.ok) {
        setStatus('success');
      } else {
        const data = await res.json().catch(() => ({}));
        setErrorMsg((data as any)?.error ?? 'Something went wrong. Please try again.');
        setStatus('error');
      }
    } catch {
      setErrorMsg('Network error. Please check your connection and try again.');
      setStatus('error');
    }
  };

  const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm(f => ({ ...f, [field]: e.target.value }));

  return (
    <section id="design-partner" className="py-24 border-t border-black/5 bg-surface relative overflow-hidden">
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] bg-hero-glow pointer-events-none opacity-50" />

      <div className="max-w-5xl mx-auto px-6 relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className="text-center mb-14"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-black/10 bg-white/60 backdrop-blur shadow-sm mb-6">
            <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
            <span className="text-[10px] font-mono tracking-widest text-steel uppercase">
              Limited Access · Design Partner Program
            </span>
          </div>
          <h2 className="text-4xl lg:text-5xl font-semibold tracking-tight text-ink mb-4">
            Be one of 5 companies<br />that shapes this.
          </h2>
          <p className="text-steel text-lg font-light max-w-2xl mx-auto leading-relaxed">
            We're looking for supply chain operators who want a production-grade AI OS — not a demo.
            You get full access free for 90 days. We get real-world feedback.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
          {/* Perks */}
          <motion.div
            initial={{ opacity: 0, x: -16 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: '-50px' }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          >
            <h3 className="text-ink font-semibold mb-6">What you get</h3>
            <div className="space-y-4">
              {perks.map((perk, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.07, duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                  className="flex items-start gap-3"
                >
                  <div className="w-5 h-5 rounded-full bg-success/10 border border-success/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Check size={11} className="text-success" />
                  </div>
                  <span className="text-ink text-sm leading-relaxed">{perk}</span>
                </motion.div>
              ))}
            </div>
            <p className="mt-10 text-[11px] font-mono text-steel">
              Limited spots · Free for 90 days · No credit card required
            </p>
          </motion.div>

          {/* Form */}
          <motion.div
            initial={{ opacity: 0, x: 16 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: '-50px' }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          >
            {status === 'success' ? (
              <motion.div
                initial={{ opacity: 0, scale: 0.96 }}
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
                      onChange={set('name')}
                      className="w-full px-3 py-2.5 rounded-lg border border-black/8 bg-white/60 text-ink text-sm focus:outline-none focus:border-accent/40 transition-colors placeholder:text-steel/40"
                      placeholder="Your name"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] font-mono text-steel uppercase tracking-widest mb-1.5 block">Company</label>
                    <input
                      required
                      value={form.company}
                      onChange={set('company')}
                      className="w-full px-3 py-2.5 rounded-lg border border-black/8 bg-white/60 text-ink text-sm focus:outline-none focus:border-accent/40 transition-colors placeholder:text-steel/40"
                      placeholder="Company name"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-[11px] font-mono text-steel uppercase tracking-widest mb-1.5 block">Work email</label>
                  <input
                    required
                    type="email"
                    value={form.email}
                    onChange={set('email')}
                    className="w-full px-3 py-2.5 rounded-lg border border-black/8 bg-white/60 text-ink text-sm focus:outline-none focus:border-accent/40 transition-colors placeholder:text-steel/40"
                    placeholder="you@company.com"
                  />
                </div>

                <div>
                  <label className="text-[11px] font-mono text-steel uppercase tracking-widest mb-1.5 block">
                    Biggest supply chain problem?
                  </label>
                  <textarea
                    required
                    rows={3}
                    value={form.problem}
                    onChange={set('problem')}
                    className="w-full px-3 py-2.5 rounded-lg border border-black/8 bg-white/60 text-ink text-sm focus:outline-none focus:border-accent/40 transition-colors resize-none placeholder:text-steel/40"
                    placeholder="e.g. We can't see disruptions until they've already hit us..."
                  />
                </div>

                {status === 'error' && (
                  <p className="text-danger text-[12px] font-mono bg-danger/5 border border-danger/20 rounded-lg px-3 py-2">
                    {errorMsg}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={status === 'submitting'}
                  className="w-full bg-ink text-paper py-3 rounded-lg font-semibold text-sm hover:bg-black transition-colors shadow-sm disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {status === 'submitting' ? (
                    <>
                      <Loader2 size={15} className="animate-spin" />
                      Submitting…
                    </>
                  ) : (
                    'Apply for Design Partner Access →'
                  )}
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
