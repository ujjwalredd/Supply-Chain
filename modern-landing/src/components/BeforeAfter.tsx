import { useRef } from 'react';
import { motion, useInView } from 'framer-motion';

const ease = [0.16, 1, 0.3, 1] as const;
const TOTAL = 90; // hours
const pct = (h: number) => `${((h / TOTAL) * 100).toFixed(2)}%`;

const BEFORE_EVENTS = [
  { time: 'T+0h',  text: 'Shipment departs — everything looks normal' },
  { time: 'T+72h', text: 'Manager discovers delay at standup — too late' },
  { time: 'T+76h', text: 'Emergency re-sourcing begins' },
  { time: 'T+84h', text: 'Production line halts — $140K impact' },
];

const AFTER_EVENTS = [
  { time: 'T+0h',   text: 'Shipment departs' },
  { time: 'T+4.2h', text: 'deviation_agent detects delay pattern' },
  { time: 'T+5h',   text: 'supplier_intel reroutes — resolved automatically' },
  { time: 'T+90h',  text: 'Delivery on time, zero human interruptions' },
];

interface BarProps {
  segments: { from: number; to: number; color: string; alpha?: number }[];
  markerH: number;
  markerColor: string;
  inView: boolean;
  delay: number;
}

function TimelineBar({ segments, markerH, markerColor, inView, delay }: BarProps) {
  return (
    <div className="relative h-5 rounded-full bg-black/[0.04] overflow-hidden">
      {segments.map((seg, i) => (
        <motion.div
          key={i}
          className="absolute top-0 bottom-0 rounded-full"
          style={{
            left: pct(seg.from),
            width: pct(seg.to - seg.from),
            background: seg.color,
            opacity: seg.alpha ?? 1,
            transformOrigin: 'left center',
          }}
          initial={{ scaleX: 0 }}
          animate={inView ? { scaleX: 1 } : { scaleX: 0 }}
          transition={{ duration: 0.85, ease, delay: delay + 0.2 + i * 0.15 }}
        />
      ))}
      {/* Marker tick */}
      <div
        className="absolute top-0 bottom-0 w-[2px] z-10"
        style={{ left: pct(markerH), background: markerColor, opacity: 0.9 }}
      />
    </div>
  );
}

export function BeforeAfter() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: '-60px' });

  return (
    <section ref={ref} className="bg-paper py-16 border-t border-black/5">
      <div className="max-w-5xl mx-auto px-6">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={inView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.6, ease }}
          className="mb-8"
        >
          <span className="text-[10px] font-mono tracking-[0.25em] text-steel uppercase block mb-2">
            The difference
          </span>
          <h2 className="text-3xl md:text-4xl font-bold text-ink tracking-tight">
            Same disruption.{' '}
            <span className="text-accent">Opposite outcome.</span>
          </h2>
          <p className="text-steel text-base mt-2 font-light">
            Supplier XJ-4421 delays +72h. The bar shows exactly when each approach responds.
          </p>
        </motion.div>

        {/* Panels */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">

          {/* BEFORE */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.7, ease, delay: 0 }}
            className="glass-card rounded-2xl p-6 flex flex-col gap-5"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-red-400" />
                <span className="text-[11px] font-mono font-bold uppercase tracking-widest text-red-500">
                  Without ForeverAutonomous
                </span>
              </div>
              <span className="text-sm font-bold px-3 py-1 rounded-full bg-red-50 text-red-500">
                $140K impact
              </span>
            </div>

            <div>
              <TimelineBar
                segments={[
                  { from: 0,  to: 72, color: '#E4E4E7', alpha: 0.8 },
                  { from: 72, to: 84, color: '#FCA5A5', alpha: 0.9 },
                  { from: 84, to: 90, color: '#EF4444', alpha: 0.85 },
                ]}
                markerH={72}
                markerColor="#EF4444"
                inView={inView}
                delay={0}
              />
              {/* Axis */}
              <div className="flex justify-between mt-1.5">
                {[0, 24, 48, 72, 90].map(h => (
                  <span key={h} className="text-[9px] font-mono text-steel/40">T+{h}h</span>
                ))}
              </div>
              {/* Marker label — inline below axis at the right position */}
              <div className="relative h-4 mt-0.5">
                <span
                  className="absolute text-[9px] font-mono text-red-400 font-semibold"
                  style={{ left: pct(72), transform: 'translateX(-50%)' }}
                >
                  Alert
                </span>
              </div>
            </div>

            <div className="space-y-2 pt-1 border-t border-black/5">
              {BEFORE_EVENTS.map((ev, i) => (
                <div key={i} className="flex items-start gap-3">
                  <span className="text-[10px] font-mono text-steel/50 w-12 flex-shrink-0 pt-px">{ev.time}</span>
                  <span className={`text-[12px] leading-relaxed ${i >= 1 ? 'text-red-500 font-medium' : 'text-ink/70'}`}>
                    {ev.text}
                  </span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* AFTER */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={inView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.7, ease, delay: 0.12 }}
            className="glass-card rounded-2xl p-6 flex flex-col gap-5"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-400" />
                <span className="text-[11px] font-mono font-bold uppercase tracking-widest text-emerald-600">
                  With ForeverAutonomous
                </span>
              </div>
              <span className="text-sm font-bold px-3 py-1 rounded-full bg-emerald-50 text-emerald-600">
                $0 impact
              </span>
            </div>

            <div>
              <TimelineBar
                segments={[
                  { from: 0,   to: 4.2, color: '#BFDBFE', alpha: 0.8 },
                  { from: 4.2, to: 5,   color: '#0070F3',  alpha: 0.9 },
                  { from: 5,   to: 90,  color: '#BBF7D0',  alpha: 0.6 },
                ]}
                markerH={4.2}
                markerColor="#0070F3"
                inView={inView}
                delay={0.12}
              />
              {/* Axis */}
              <div className="flex justify-between mt-1.5">
                {[0, 24, 48, 72, 90].map(h => (
                  <span key={h} className="text-[9px] font-mono text-steel/40">T+{h}h</span>
                ))}
              </div>
              {/* Marker label */}
              <div className="relative h-4 mt-0.5">
                <span
                  className="absolute text-[9px] font-mono text-blue-500 font-semibold"
                  style={{ left: pct(4.2), transform: 'translateX(-10%)' }}
                >
                  Detected
                </span>
              </div>
            </div>

            <div className="space-y-2 pt-1 border-t border-black/5">
              {AFTER_EVENTS.map((ev, i) => (
                <div key={i} className="flex items-start gap-3">
                  <span className="text-[10px] font-mono text-steel/50 w-12 flex-shrink-0 pt-px">{ev.time}</span>
                  <span className={`text-[12px] leading-relaxed ${i === 1 || i === 2 ? 'text-accent font-medium' : 'text-ink/70'}`}>
                    {ev.text}
                  </span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ delay: 1.2 }}
          className="text-center text-[11px] font-mono text-steel/40 mt-6"
        >
          Both timelines span 90 hours — the red appears at 80% vs 5%
        </motion.p>
      </div>
    </section>
  );
}
