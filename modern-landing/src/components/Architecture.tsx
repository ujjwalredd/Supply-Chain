import { useRef } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import { Database, Zap, Layers, Server } from 'lucide-react';

// Simulated raw data that transforms through the pipeline
const RAW_DATA_LINES = [
  '{ "po_id": "PO-4422", "status": "??", qty: null }',
  '{ vendor: "OceanLine", port: "SH-04" }',
  '{ "inv_level": 240, "loc": "wh_east" }',
];
const CLEAN_DATA_LINES = [
  '{ "order_id": "PO-4422", "status": "DELAYED" }',
  '{ "vendor_id": "VEN-012", "port": "CNSHA" }',
  '{ "inventory": 240, "warehouse": "WH-EAST" }',
];

export function Architecture() {
  const containerRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start end", "end start"]
  });

  // Camera dive effect
  const cameraScale = useTransform(scrollYProgress, [0, 0.3, 0.7, 1], [0.85, 1, 1, 0.95]);
  const cameraY = useTransform(scrollYProgress, [0, 0.3], [60, 0]);
  const cameraOpacity = useTransform(scrollYProgress, [0, 0.2], [0.3, 1]);

  // Pipeline draw progress  
  const pipeProgress = useTransform(scrollYProgress, [0.1, 0.6], [0, 1]);

  // Raw data opacity (fades in then out as it gets "processed")
  const rawOpacity = useTransform(scrollYProgress, [0.1, 0.25, 0.45, 0.6], [0, 1, 1, 0.6]);
  const cleanOpacity = useTransform(scrollYProgress, [0.15, 0.35], [0, 1]);

  // Card stagger transforms
  const card1Y = useTransform(scrollYProgress, [0.1, 0.3], [40, 0]);
  const card2Y = useTransform(scrollYProgress, [0.2, 0.4], [40, 0]);
  const card3Y = useTransform(scrollYProgress, [0.3, 0.5], [40, 0]);
  const card4Y = useTransform(scrollYProgress, [0.4, 0.6], [40, 0]);
  const cardYs = [card1Y, card2Y, card3Y, card4Y];

  const stack = [
    { name: 'Kafka & ksqlDB', desc: 'Real-time 5-min tumbling windows processing supply chain telemetry.', icon: Zap, color: 'text-warning border-warning/20 bg-warning/5', accentHex: '#F59E0B' },
    { name: 'Dagster Lakehouse', desc: 'Medallion architecture managing Bronze/Silver/Gold analytics Parquet.', icon: Layers, color: 'text-success border-success/20 bg-success/5', accentHex: '#10B981' },
    { name: 'Event-Sourced PostgreSQL', desc: 'Point-in-time recovery via immutable ledger. Fast CRUD via FastAPI.', icon: Database, color: 'text-accent border-accent/20 bg-accent/5', accentHex: '#0070F3' },
    { name: 'MLflow & OpenTelemetry', desc: 'XGBoost forecasting model registry + end-to-end Jaeger distributed tracing.', icon: Server, color: 'text-ink border-ink/10 bg-surface', accentHex: '#09090B' },
  ];

  return (
    <section id="architecture" className="py-32 bg-surface relative noise-texture overflow-hidden" ref={containerRef}>
      {/* Subtle ambient depth */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-accent/[0.02] to-transparent pointer-events-none" />
      
      <motion.div 
        style={{ scale: cameraScale, y: cameraY, opacity: cameraOpacity }}
        className="max-w-7xl mx-auto px-6 text-center relative z-10"
      >
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
          <h2 className="text-sm font-mono text-steel uppercase tracking-widest mb-4 font-semibold">Enterprise Grade Infrastructure</h2>
          <h3 className="text-3xl lg:text-4xl font-semibold tracking-tight text-ink mb-6">
            A modern stack built for scale.<br />No black boxes.
          </h3>
          <p className="text-steel text-base max-w-xl mx-auto mb-16 font-light">
            Watch raw, chaotic supply chain data enter the pipeline and emerge as structured, actionable intelligence.
          </p>
        </motion.div>

        {/* ═══ Live Data Transformation Strip ═══ */}
        <div className="mb-16 relative">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr_auto_1fr] gap-0 md:gap-4 max-w-5xl mx-auto items-stretch">
            
            {/* Raw data (chaotic) */}
            <motion.div 
              style={{ opacity: rawOpacity }}
              className="bg-white rounded-xl border border-warning/20 p-6 text-left shadow-sm flex flex-col"
            >
              <div className="text-[10px] font-mono font-bold text-warning uppercase mb-4 tracking-widest flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-warning" />
                Raw Ingestion
              </div>
              <div className="space-y-2.5 font-mono text-[11px] flex-1">
                {RAW_DATA_LINES.map((line, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -20 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.15, duration: 0.5 }}
                    className="text-ink/60 bg-warning/[0.06] px-3 py-2 rounded-lg break-all leading-relaxed border border-warning/10"
                  >
                    {line}
                  </motion.div>
                ))}
              </div>
            </motion.div>

            {/* Arrow 1 */}
            <div className="hidden md:flex items-center justify-center">
              <motion.div
                animate={{ x: [0, 6, 0] }}
                transition={{ repeat: Infinity, duration: 2, ease: "easeInOut" }}
                className="flex flex-col items-center gap-1"
              >
                <div className="w-8 h-8 rounded-full bg-white border border-black/10 shadow-sm flex items-center justify-center text-accent font-bold text-sm">
                  →
                </div>
              </motion.div>
            </div>
            {/* Mobile arrow */}
            <div className="flex md:hidden items-center justify-center py-3">
              <div className="w-8 h-8 rounded-full bg-white border border-black/10 shadow-sm flex items-center justify-center text-accent font-bold text-sm rotate-90">→</div>
            </div>

            {/* Processing (Dagster Medallion) */}
            <motion.div 
              style={{ opacity: pipeProgress }}
              className="bg-white rounded-xl border border-success/20 p-6 text-left shadow-sm flex flex-col"
            >
              <div className="text-[10px] font-mono font-bold text-success uppercase mb-4 tracking-widest flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-success" />
                Medallion Engine
              </div>
              <div className="space-y-3 flex-1 flex flex-col justify-center">
                {['Bronze → Silver', 'Silver → Gold', 'Validation ✓'].map((step, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, scale: 0.9 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.3 + i * 0.2, duration: 0.4 }}
                    className="flex items-center gap-3 text-sm font-mono bg-success/[0.06] px-3 py-2 rounded-lg border border-success/10"
                  >
                    <motion.div 
                      animate={{ scale: [1, 1.3, 1] }}
                      transition={{ repeat: Infinity, duration: 2, delay: i * 0.4 }}
                      className="w-2 h-2 rounded-full bg-success shadow-sm flex-shrink-0"
                    />
                    <span className="text-ink/60">{step}</span>
                  </motion.div>
                ))}
              </div>
            </motion.div>

            {/* Arrow 2 */}
            <div className="hidden md:flex items-center justify-center">
              <motion.div
                animate={{ x: [0, 6, 0] }}
                transition={{ repeat: Infinity, duration: 2, ease: "easeInOut", delay: 0.5 }}
                className="flex flex-col items-center gap-1"
              >
                <div className="w-8 h-8 rounded-full bg-white border border-black/10 shadow-sm flex items-center justify-center text-accent font-bold text-sm">
                  →
                </div>
              </motion.div>
            </div>
            {/* Mobile arrow */}
            <div className="flex md:hidden items-center justify-center py-3">
              <div className="w-8 h-8 rounded-full bg-white border border-black/10 shadow-sm flex items-center justify-center text-accent font-bold text-sm rotate-90">→</div>
            </div>

            {/* Clean data (structured) */}
            <motion.div 
              style={{ opacity: cleanOpacity }}
              className="bg-white rounded-xl border border-accent/20 p-6 text-left shadow-sm flex flex-col"
            >
              <div className="text-[10px] font-mono font-bold text-accent uppercase mb-4 tracking-widest flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-accent" />
                Canonical Output
              </div>
              <div className="space-y-2.5 font-mono text-[11px] flex-1">
                {CLEAN_DATA_LINES.map((line, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: 20 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.5 + i * 0.15, duration: 0.5 }}
                    className="text-ink bg-accent/[0.06] px-3 py-2 rounded-lg break-all leading-relaxed border border-accent/10"
                  >
                    {line}
                  </motion.div>
                ))}
              </div>
            </motion.div>
          </div>
        </div>

        {/* ═══ Stack Cards with Scroll-Staggered Entry ═══ */}
        <div className="relative">
          {/* Animated Flow SVG */}
          <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-20 pointer-events-none hidden lg:block z-0">
            <svg className="w-full h-full" preserveAspectRatio="none" viewBox="0 0 1000 100">
              {/* Background Tracks (Faint) */}
              <path d="M 125,50 L 375,50" stroke="#E4E4E7" strokeWidth="2" strokeDasharray="4 4" fill="none" opacity="0.5" />
              <path d="M 375,50 L 625,50" stroke="#E4E4E7" strokeWidth="2" strokeDasharray="4 4" fill="none" opacity="0.5" />
              <path d="M 625,50 L 875,50" stroke="#E4E4E7" strokeWidth="2" strokeDasharray="4 4" fill="none" opacity="0.5" />

              {/* Scroll Triggered Draw Tracks */}
              <motion.path d="M 125,50 L 375,50" stroke="#F59E0B" strokeWidth="2" fill="none" style={{ pathLength: pipeProgress }} />
              <motion.path d="M 375,50 L 625,50" stroke="#10B981" strokeWidth="2" fill="none" style={{ pathLength: pipeProgress }} />
              <motion.path d="M 625,50 L 875,50" stroke="#0070F3" strokeWidth="2" fill="none" style={{ pathLength: pipeProgress }} />

              {/* Persistent Animated Packets */}
              <circle r="4" fill="#F59E0B" className="shadow-lg">
                <animateMotion dur="2.5s" repeatCount="indefinite" path="M 125,50 L 375,50" keyPoints="0;1" keyTimes="0;1" calcMode="linear" />
              </circle>
              <circle r="4" fill="#10B981">
                <animateMotion dur="2.5s" repeatCount="indefinite" path="M 375,50 L 625,50" begin="0.8s" keyPoints="0;1" keyTimes="0;1" calcMode="linear" />
              </circle>
              <circle r="4" fill="#0070F3">
                <animateMotion dur="2.5s" repeatCount="indefinite" path="M 625,50 L 875,50" begin="1.6s" keyPoints="0;1" keyTimes="0;1" calcMode="linear" />
              </circle>
            </svg>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 text-left relative z-10">
            {stack.map((item, idx) => {
              const Icon = item.icon;
              return (
                <motion.div
                  key={idx}
                  style={{ y: cardYs[idx] }}
                  initial={{ opacity: 0 }}
                  whileInView={{ opacity: 1 }}
                  viewport={{ once: true, margin: '-50px' }}
                  transition={{ delay: idx * 0.1, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                  className="liquid-glass p-6 rounded-2xl flex flex-col relative overflow-hidden group hover:-translate-y-2 transition-transform duration-700 ease-[cubic-bezier(0.16,1,0.3,1)]"
                >
                  {/* Hover glow accent */}
                  <div 
                    className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none"
                    style={{ background: `radial-gradient(circle at 50% 0%, ${item.accentHex}10 0%, transparent 70%)` }}
                  />

                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center border mb-6 relative z-10 bg-white shadow-sm ${item.color}`}>
                    <Icon size={24} />
                  </div>
                  <h4 className="text-ink font-semibold mb-2 relative z-10">{item.name}</h4>
                  <p className="text-steel text-sm leading-relaxed relative z-10">{item.desc}</p>
                </motion.div>
              )
            })}
          </div>
        </div>
      </motion.div>
    </section>
  );
}
