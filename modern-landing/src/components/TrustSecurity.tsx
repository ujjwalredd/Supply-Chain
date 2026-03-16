import { motion } from 'framer-motion';
import {
  Trash2, UserCheck, Lock, GitBranch, ShieldCheck,
  Link2, ScanLine, Database, FlaskConical, Tags, FileCheck2,
  KeyRound, Bug, CheckCircle2, RefreshCw,
} from 'lucide-react';

const ease = [0.16, 1, 0.3, 1] as const;

// ── Three governance pillars ─────────────────────────────────────────────────

const AI_SECURITY = [
  {
    Icon: KeyRound,
    title: 'HMAC-Signed Corrections',
    desc: 'Every orchestrator-to-agent correction is signed with HMAC-SHA256. Agents reject any unsigned or tampered correction before acting on it — a rogue process cannot steer the fleet.',
  },
  {
    Icon: Bug,
    title: 'Prompt Injection Defense',
    desc: 'All external data — CSV values, Kafka payloads, supplier notes, API responses — passes through 8 regex patterns before it touches an LLM prompt. Instruction overrides, role hijacks, and model-delimiter injections are detected and quarantined.',
  },
  {
    Icon: FlaskConical,
    title: '8-Gate Code Sandbox',
    desc: 'AI-generated loaders and feature transforms pass syntax check → sandboxed execution → sample validation → schema match → timeout kill → distribution sanity → variance check → novelty/correlation gate before any real data is touched.',
  },
];

const AUDIT_PROVENANCE = [
  {
    Icon: Link2,
    title: 'Hash-Chained Immutable Audit Log',
    desc: 'Every agent decision is written to agent_audit_log_v2 with a SHA-256 chain: each row stores the previous row\'s hash. Tampering with any entry breaks every subsequent hash — the chain self-detects compromise.',
  },
  {
    Icon: ScanLine,
    title: 'Decision Provenance',
    desc: 'For every autonomous action, the system stores: trigger event, data sources consulted, LLM prompt hash, response hash, confidence score, and outcome action. Full replay is possible for any decision at any point in time.',
  },
  {
    Icon: FileCheck2,
    title: 'Correction Outcome Tracking',
    desc: 'When the orchestrator issues a correction, its effectiveness is measured 15 minutes later — comparing agent status before and after. Ineffective corrections surface automatically for human review.',
  },
];

const DATA_GOVERNANCE = [
  {
    Icon: Tags,
    title: 'Per-Column Data Classification',
    desc: 'Every column in every table carries a sensitivity label: PUBLIC, INTERNAL, CONFIDENTIAL, or PII — with retention policy attached. Labels are queryable, auditable, and block unauthorised data flows.',
  },
  {
    Icon: Database,
    title: 'Data Lineage Graph',
    desc: 'Every pipeline run writes to lineage_events — inputs consumed, output produced, job name, runtime. The /lineage API returns a live graph: nodes for datasets and jobs, edges for data flow. Nothing moves invisibly.',
  },
  {
    Icon: UserCheck,
    title: 'Human Escalation Workflow',
    desc: 'Situations requiring human judgement — 3+ degraded agents, systemic anomalies, confidence below threshold — trigger a human_escalations record. Operators acknowledge and resolve via the dashboard. Resolution time is tracked.',
  },
];

// ── Original security pillars (kept as a secondary row) ─────────────────────

const TRUST_PILLARS = [
  {
    Icon: Trash2,
    title: 'Right to Delete — Instantly',
    desc: 'One API call wipes every record: orders, supplier data, agent audit logs, ML training rows, Kafka events, Redis state. Hard delete, not soft. No retention held beyond 24 hours unless you configure it.',
  },
  {
    Icon: Lock,
    title: 'Self-Hosted. Your Infrastructure.',
    desc: 'ForeverAutonomous runs entirely on your own servers via Docker Compose. Your data never leaves your environment. No cloud dependency, no SaaS vendor holding your operational data.',
  },
  {
    Icon: GitBranch,
    title: 'Open Source. No Black Boxes.',
    desc: 'Every line of code powering the agents, orchestrator, and pipeline is public on GitHub under AGPL-3.0. Your engineers can audit exactly what runs on your data.',
  },
  {
    Icon: ShieldCheck,
    title: 'Bias & Drift Monitoring',
    desc: 'MLflowGuardianAgent watches ROC-AUC continuously. A >5% drop triggers automatic retraining. Promotion decisions require tool_use structured reasoning — no free-text hallucination path to production.',
  },
  {
    Icon: RefreshCw,
    title: 'Event-Sourced State',
    desc: 'Every order state change is an immutable append to order_events with a unique (order_id, version) constraint. Point-in-time recovery to any prior state is a single API call.',
  },
  {
    Icon: CheckCircle2,
    title: 'Human Always Has Final Say',
    desc: 'When confidence drops below your threshold or impact exceeds your limit, the system stops and waits for human approval. The escalation gate is enforced in code — no operator can bypass it.',
  },
];

const COMMITMENTS = [
  'No data sold or shared with third parties',
  'All LLM calls use your own Anthropic API key',
  'Hard-delete endpoint available via API and CLI',
  'Encryption at rest and in transit (TLS 1.3)',
  'HMAC-SHA256 signed agent-to-agent corrections',
  '8-gate sandbox before any AI code runs on real data',
  'SHA-256 hash-chained immutable audit log',
  'Per-column data classification (PUBLIC / INTERNAL / CONFIDENTIAL / PII)',
  'Full decision provenance — every AI action is replayable',
  'Human escalation workflow with resolution-time tracking',
  '348+ automated security and integrity tests on every release',
  'Point-in-time recovery via immutable event ledger',
];

// ── Reusable card group ───────────────────────────────────────────────────────

function PillarGroup({
  label,
  pillars,
  startDelay = 0,
}: {
  label: string;
  pillars: { Icon: React.ElementType; title: string; desc: string }[];
  startDelay?: number;
}) {
  return (
    <div>
      <p className="text-[10px] font-mono uppercase tracking-widest text-steel/50 mb-3">{label}</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-x-8 gap-y-6">
        {pillars.map((p, i) => {
          const Icon = p.Icon;
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-40px' }}
              transition={{ delay: startDelay + i * 0.09, duration: 0.75, ease }}
              className="flex flex-col group"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-white/60 backdrop-blur-sm border border-white/40 shadow-sm group-hover:shadow-md group-hover:border-accent/20 group-hover:scale-110 transition-[transform,box-shadow,border-color] duration-500">
                  <Icon size={18} className="text-ink group-hover:text-accent transition-colors duration-300" />
                </div>
                <h4 className="text-ink font-semibold text-sm leading-snug">{p.title}</h4>
              </div>
              <p className="text-steel text-sm leading-relaxed">{p.desc}</p>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function TrustSecurity() {
  return (
    <section className="py-10 bg-paper relative z-10 border-b border-black/5 noise-texture overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 relative z-10 space-y-8">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.8, ease }}
          className="max-w-3xl"
        >
          <h2 className="text-sm font-mono text-accent uppercase tracking-widest mb-3 font-semibold">
            Data Governance · AI Security · Trustworthiness
          </h2>
          <h3 className="text-3xl lg:text-4xl font-semibold tracking-tight text-ink mb-3">
            Autonomous. Not unaccountable.
          </h3>
          <p className="text-steel text-lg font-light leading-relaxed">
            Three independent layers — AI security to harden every model interaction,
            immutable provenance to make every decision replayable, and data governance
            to control exactly what moves where and who can see it.
            Each layer runs in production today, in the same Docker stack.
          </p>
        </motion.div>

        {/* Layer badges */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-40px' }}
          transition={{ duration: 0.6, ease, delay: 0.1 }}
          className="flex flex-wrap gap-3"
        >
          {[
            { dot: 'bg-red-400',    label: 'AI Security' },
            { dot: 'bg-violet-400', label: 'Audit & Provenance' },
            { dot: 'bg-emerald-400',label: 'Data Governance' },
            { dot: 'bg-sky-400',    label: 'Platform Trust' },
          ].map(({ dot, label }) => (
            <span
              key={label}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-black/8 bg-surface text-[11px] font-mono text-steel tracking-wide"
            >
              <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
              {label}
            </span>
          ))}
        </motion.div>

        {/* Pillar group 1 — AI Security */}
        <PillarGroup label="Layer 1 — AI Security" pillars={AI_SECURITY} startDelay={0} />

        <div className="h-px w-full bg-gradient-to-r from-black/6 via-black/3 to-transparent" />

        {/* Pillar group 2 — Audit & Provenance */}
        <PillarGroup label="Layer 2 — Audit & Provenance" pillars={AUDIT_PROVENANCE} startDelay={0} />

        <div className="h-px w-full bg-gradient-to-r from-black/6 via-black/3 to-transparent" />

        {/* Pillar group 3 — Data Governance */}
        <PillarGroup label="Layer 3 — Data Governance" pillars={DATA_GOVERNANCE} startDelay={0} />

        <div className="h-px w-full bg-gradient-to-r from-black/6 via-black/3 to-transparent" />

        {/* Platform trust row */}
        <PillarGroup label="Layer 4 — Platform Trust" pillars={TRUST_PILLARS} startDelay={0} />

        {/* Commitments strip */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.6, ease, delay: 0.3 }}
          className="rounded-2xl border border-black/5 bg-surface p-4 md:p-6"
        >
          <p className="text-[10px] font-mono uppercase tracking-widest text-steel mb-4">
            Our commitments — every deployment, every release
          </p>
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
