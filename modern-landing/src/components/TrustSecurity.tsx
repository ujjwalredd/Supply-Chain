import { motion } from 'framer-motion';
import { Trash2, Eye, UserCheck, Lock, GitBranch, ShieldCheck } from 'lucide-react';

const ease = [0.16, 1, 0.3, 1] as const;

const PILLARS = [
  {
    Icon: Trash2,
    title: 'Right to Delete — Instantly',
    desc: 'One API call wipes every record: orders, supplier data, agent audit logs, ML training rows, Kafka events, Redis state. Hard delete, not soft. No retention held beyond 24 hours unless you configure it.',
  },
  {
    Icon: Eye,
    title: 'Full Audit Trail on Every Action',
    desc: 'Every autonomous decision — every reroute, every escalation, every model promotion — written to an immutable audit log with timestamp, agent ID, confidence score, and full reasoning.',
  },
  {
    Icon: UserCheck,
    title: 'Human Always Has Final Say',
    desc: 'When confidence drops below your threshold or impact exceeds your limit, the system stops and waits for human approval. The escalation gate is enforced in code — no operator can bypass it.',
  },
  {
    Icon: Lock,
    title: 'Self-Hosted. Your Infrastructure.',
    desc: 'ForeverAutonomous runs entirely on your own servers via Docker Compose. Your data never leaves your environment. No cloud dependency, no SaaS vendor holding your operational data.',
  },
  {
    Icon: GitBranch,
    title: 'Open Source. No Black Boxes.',
    desc: 'Every line of code powering the agents, orchestrator, and pipeline is public on GitHub under AGPL-3.0. Your engineers can audit exactly what runs on your data. No hidden logic, ever.',
  },
  {
    Icon: ShieldCheck,
    title: 'Generated Code Never Runs Unvalidated',
    desc: 'When AI generates a loader or feature transformation, it passes 5 mandatory gates before touching real data: syntax check, sandboxed execution, sample validation, schema check, timeout kill.',
  },
];

const COMMITMENTS = [
  'No data sold or shared with third parties',
  'All LLM calls use your own Anthropic API key',
  'Hard-delete endpoint available via API and CLI',
  'Encryption at rest and in transit (TLS 1.3)',
  '203 automated security and integrity tests on every release',
  'Point-in-time recovery via immutable event ledger',
];

export function TrustSecurity() {
  return (
    <section className="py-24 bg-paper relative z-10 border-b border-black/5 noise-texture overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 relative z-10">

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.8, ease }}
          className="mb-16 max-w-3xl"
        >
          <h2 className="text-sm font-mono text-accent uppercase tracking-widest mb-4 font-semibold">Security & Trust</h2>
          <h3 className="text-3xl lg:text-4xl font-semibold tracking-tight text-ink mb-6">
            Autonomous. Not unaccountable.
          </h3>
          <p className="text-steel text-lg font-light leading-relaxed">
            Every action is logged, every deletion is real, and your team stays in control of what the system can and cannot do.
          </p>
        </motion.div>

        {/* Pillar grid — matches Capabilities card style */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-12 mb-16">
          {PILLARS.map((p, i) => {
            const Icon = p.Icon;
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ delay: i * 0.1, duration: 0.8, ease }}
                className="flex flex-col group"
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-white/60 backdrop-blur-sm border border-white/40 shadow-sm group-hover:shadow-md group-hover:border-accent/20 group-hover:scale-110 transition-all duration-500">
                    <Icon size={18} className="text-ink group-hover:text-accent transition-colors duration-300" />
                  </div>
                  <h4 className="text-ink font-semibold">{p.title}</h4>
                </div>
                <p className="text-steel text-sm leading-relaxed">{p.desc}</p>
              </motion.div>
            );
          })}
        </div>

        {/* Commitments strip */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.6, ease, delay: 0.4 }}
          className="rounded-2xl border border-black/5 bg-surface p-6 md:p-8"
        >
          <p className="text-[10px] font-mono uppercase tracking-widest text-steel mb-5">Our commitments</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {COMMITMENTS.map((c, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <div className="w-1 h-1 rounded-full bg-accent mt-2 flex-shrink-0" />
                <span className="text-[12px] text-steel leading-relaxed">{c}</span>
              </div>
            ))}
          </div>
        </motion.div>

      </div>
    </section>
  );
}
