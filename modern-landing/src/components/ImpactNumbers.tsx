import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';

const METRICS = [
  { value: '4.2h',  label: 'Earlier than your team',   sub: 'avg lead time before disruption hits',         color: '#0070F3' },
  { value: '0',     label: 'Human interventions',       sub: 'agents resolve deviations automatically',      color: '#09090B' },
  { value: '13',    label: 'Agents running 24/7',       sub: 'each on its own schedule, self-healing',       color: '#0070F3' },
  { value: '<60s',  label: 'CSV to live pipeline',      sub: 'drop any file, schema is auto-inferred',       color: '#09090B' },
];

export function ImpactNumbers() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-80px' });

  return (
    <section ref={ref} className="bg-paper border-t border-b border-black/5 py-16">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-2 md:grid-cols-4 divide-x divide-black/5">
          {METRICS.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 16 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: i * 0.08 }}
              className="flex flex-col items-center text-center px-6 py-8"
            >
              <div
                className="text-[56px] sm:text-[72px] font-bold tracking-tighter leading-none mb-2"
                style={{ color: m.color }}
              >
                {m.value}
              </div>
              <p className="text-ink font-semibold text-base mb-1">{m.label}</p>
              <p className="text-steel text-sm font-mono max-w-[180px] leading-snug">{m.sub}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
