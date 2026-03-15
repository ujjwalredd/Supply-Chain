import { useState } from 'react';
import { motion, AnimatePresence, LayoutGroup } from 'framer-motion';
import { ShieldCheck, UserCheck, Settings2, ArrowRight } from 'lucide-react';

const DEVIATIONS = [
  { id: 1, name: 'Delay at Port (3 Days)', confidence: 0.85, impact: 15000 },
  { id: 2, name: 'Supplier Bankruptcy', confidence: 0.45, impact: 450000 },
  { id: 3, name: 'Stockout Risk (Raw Materials)', confidence: 0.92, impact: 8000 },
  { id: 4, name: 'Vessel Congestion Reroute', confidence: 0.78, impact: 120000 },
  { id: 5, name: 'Weather Event (Typhoon)', confidence: 0.60, impact: 35000 },
  { id: 6, name: 'Warehouse Fire (Tier 2)', confidence: 0.99, impact: 850000 },
];

// Smooth number formatter with animation
function SlotNumber({ value, prefix = '' }: { value: number; prefix?: string }) {
  const formatted = value.toLocaleString();
  return (
    <span className="inline-flex items-center font-mono">
      {prefix}
      {formatted.split('').map((char, i) => (
        <motion.span 
          key={`${value}-${i}`}
          initial={{ y: 12, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: i * 0.03, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          className="inline-block"
        >
          {char}
        </motion.span>
      ))}
    </span>
  );
}

export function GlassBox() {
  const [maxImpact, setMaxImpact] = useState(250000);
  const [minConfidence, setMinConfidence] = useState(0.70);

  const getStatus = (dev: typeof DEVIATIONS[0]) => {
    return (dev.confidence >= minConfidence && dev.impact <= maxImpact) ? 'EXECUTED' : 'ESCALATED';
  };

  const executed = DEVIATIONS.filter(d => getStatus(d) === 'EXECUTED');
  const escalated = DEVIATIONS.filter(d => getStatus(d) === 'ESCALATED');

  return (
    <section className="py-24 bg-surface border-b border-black/5 relative overflow-hidden noise-texture">
      {/* Ambient glow */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] bg-accent/[0.03] blur-[120px] rounded-full" />
      </div>

      <div className="max-w-7xl mx-auto px-6 relative z-10">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-sm font-mono text-accent uppercase tracking-widest mb-4 font-semibold">Interactive Playground</h2>
          <h3 className="text-3xl lg:text-4xl font-semibold tracking-tight text-ink mb-6">
            Glass-Box Policy Engine
          </h3>
          <p className="text-steel text-lg font-light leading-relaxed">
            Drag the sliders to adjust your organization's risk tolerance. The AI ActionExecutor instantly re-evaluates which decisions run autonomously and which require human review.
          </p>
        </div>

        <LayoutGroup>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
            {/* Controls — Liquid Glass Panel */}
            <div className="lg:col-span-4 space-y-8 liquid-glass p-8 rounded-2xl relative z-10">
              <div className="flex items-center gap-3 mb-6 pb-6 border-b border-black/5">
                <Settings2 className="text-accent" size={24} />
                <h4 className="text-lg font-semibold text-ink">Global Policies</h4>
              </div>

              <div className="space-y-4">
                <div className="flex justify-between items-end">
                  <label className="text-sm font-medium text-ink">Max Auto-Execute Limit</label>
                  <span className="text-xs font-mono text-accent"><SlotNumber value={maxImpact} prefix="$" /></span>
                </div>
                <input 
                  type="range" 
                  min="0" max="1000000" step="10000"
                  value={maxImpact}
                  onChange={(e) => setMaxImpact(Number(e.target.value))}
                  className="w-full accent-accent h-2 bg-black/5 rounded-lg appearance-none cursor-pointer"
                />
                <p className="text-[11px] text-steel">Deviations costing more than this will be escalated.</p>
              </div>

              <div className="space-y-4 pt-6 border-t border-black/5">
                <div className="flex justify-between items-end">
                  <label className="text-sm font-medium text-ink">Min Confidence Threshold</label>
                  <span className="text-xs font-mono text-accent">{(minConfidence * 100).toFixed(0)}%</span>
                </div>
                <input 
                  type="range" 
                  min="0" max="1" step="0.01"
                  value={minConfidence}
                  onChange={(e) => setMinConfidence(Number(e.target.value))}
                  className="w-full accent-accent h-2 bg-black/5 rounded-lg appearance-none cursor-pointer"
                />
                <p className="text-[11px] text-steel">Reasoning schemas below this score require human review.</p>
              </div>
            </div>

            {/* Visualization Buckets */}
            <div className="lg:col-span-8 grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-0 md:gap-4 items-stretch">

              {/* Executed Bucket */}
              <div className="bg-success/[0.03] backdrop-blur-sm border border-success/15 rounded-2xl p-6 flex flex-col min-h-[420px] relative overflow-hidden">
                {/* Subtle shine */}
                <div className="absolute top-0 left-0 right-0 h-24 bg-gradient-to-b from-white/40 to-transparent pointer-events-none rounded-t-2xl" />
                
                <div className="flex items-center gap-3 mb-6 relative z-10">
                  <ShieldCheck className="text-success" size={20} />
                  <h4 className="font-semibold text-success-dark">Autonomous Execution</h4>
                  <motion.span 
                    key={executed.length}
                    initial={{ scale: 1.4 }}
                    animate={{ scale: 1 }}
                    className="ml-auto text-xs font-mono bg-success/10 text-success px-2 py-1 rounded-full"
                  >
                    {executed.length}
                  </motion.span>
                </div>
                <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-hide flex flex-col items-center relative z-10">
                  <AnimatePresence mode="popLayout">
                    {executed.map(dev => (
                      <motion.div 
                        layout
                        layoutId={`dev-${dev.id}`}
                        initial={{ opacity: 0, scale: 0.85, y: 30, filter: "blur(4px)" }}
                        animate={{ opacity: 1, scale: 1, y: 0, filter: "blur(0px)" }}
                        exit={{ opacity: 0, scale: 0.85, y: -30, filter: "blur(4px)" }}
                        transition={{ type: "spring", bounce: 0.25, duration: 0.7 }}
                        key={dev.id}
                        className="w-full liquid-glass rounded-xl p-4 !border-success/20"
                      >
                        <h5 className="font-medium text-sm text-ink mb-2">{dev.name}</h5>
                        <div className="flex justify-between text-xs font-mono">
                          <span className="text-steel">Conf: {(dev.confidence * 100).toFixed(0)}%</span>
                          <span className="text-steel">Impact: ${dev.impact.toLocaleString()}</span>
                        </div>
                      </motion.div>
                    ))}
                    {executed.length === 0 && (
                      <motion.div layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-sm text-success/60 text-center mt-10">
                        No deviations meet the autonomous criteria.
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>

              {/* Center Arrow Column */}
              <div className="hidden md:flex items-center justify-center">
                <div className="w-10 h-10 rounded-full bg-white border border-black/10 shadow-sm flex items-center justify-center">
                  <ArrowRight size={16} className="text-accent" />
                </div>
              </div>
              {/* Mobile arrow */}
              <div className="flex md:hidden items-center justify-center py-3">
                <div className="w-10 h-10 rounded-full bg-white border border-black/10 shadow-sm flex items-center justify-center rotate-90">
                  <ArrowRight size={16} className="text-accent" />
                </div>
              </div>

              {/* Escalated Bucket */}
              <div className="bg-warning/[0.03] backdrop-blur-sm border border-warning/15 rounded-2xl p-6 flex flex-col min-h-[420px] relative overflow-hidden">
                <div className="absolute top-0 left-0 right-0 h-24 bg-gradient-to-b from-white/40 to-transparent pointer-events-none rounded-t-2xl" />

                <div className="flex items-center gap-3 mb-6 relative z-10">
                  <UserCheck className="text-warning-dark" size={20} />
                  <h4 className="font-semibold text-warning-dark">Human Escalation</h4>
                  <motion.span 
                    key={escalated.length}
                    initial={{ scale: 1.4 }}
                    animate={{ scale: 1 }}
                    className="ml-auto text-xs font-mono bg-warning/10 text-warning-dark px-2 py-1 rounded-full"
                  >
                    {escalated.length}
                  </motion.span>
                </div>
                <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-hide flex flex-col items-center relative z-10">
                  <AnimatePresence mode="popLayout">
                    {escalated.map(dev => {
                      const reason: string[] = [];
                      if (dev.confidence < minConfidence) reason.push(`Low Conf (${(dev.confidence * 100).toFixed(0)}%)`);
                      if (dev.impact > maxImpact) reason.push(`High Cost ($${dev.impact.toLocaleString()})`);

                      return (
                        <motion.div 
                          layout
                          layoutId={`dev-${dev.id}`}
                          initial={{ opacity: 0, scale: 0.85, y: 30, filter: "blur(4px)" }}
                          animate={{ opacity: 1, scale: 1, y: 0, filter: "blur(0px)" }}
                          exit={{ opacity: 0, scale: 0.85, y: -30, filter: "blur(4px)" }}
                          transition={{ type: "spring", bounce: 0.25, duration: 0.7 }}
                          key={dev.id}
                          className="w-full liquid-glass rounded-xl p-4 !border-warning/20"
                        >
                          <h5 className="font-medium text-sm text-ink mb-2">{dev.name}</h5>
                          <div className="flex justify-between items-center">
                            <span className="text-[10px] font-mono bg-warning/10 text-warning-dark px-2 py-0.5 rounded">
                              {reason.join(" & ")}
                            </span>
                          </div>
                        </motion.div>
                      )
                    })}
                    {escalated.length === 0 && (
                      <motion.div layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-sm text-warning/60 text-center mt-10">
                        All deviations are being handled autonomously.
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>

            </div>
          </div>
        </LayoutGroup>
      </div>
    </section>
  );
}
