import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, BrainCircuit, ActivitySquare, RefreshCw } from 'lucide-react';

export function AIFeature() {
  const [isSimulatingFallback, setIsSimulatingFallback] = useState(false);
  const [isGlitching, setIsGlitching] = useState(false);
  const terminalRef = useRef<HTMLDivElement>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  const [displayData, setDisplayData] = useState({
    confidence: "0.982",
    model: "claude-sonnet-4-6",
    quality: "0.94",
    escalated: "false",
    confidenceColor: "text-success",
    qualityColor: "text-success",
    escalatedColor: "text-warning"
  });

  // Mouse tracking for holographic tilt
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!terminalRef.current) return;
    const rect = terminalRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    setMousePos({ x, y });
  };

  const handleMouseLeave = () => {
    setMousePos({ x: 0, y: 0 });
  };

  useEffect(() => {
    if (isSimulatingFallback) {
      setIsGlitching(true);
      setTimeout(() => {
        setDisplayData({
          confidence: "0.312",
          model: "claude-sonnet-4-6",
          quality: "0.28",
          escalated: "true",
          confidenceColor: "text-danger",
          qualityColor: "text-danger",
          escalatedColor: "text-success"
        });
        setTimeout(() => setIsGlitching(false), 400);
      }, 300);
    } else {
      setDisplayData({
        confidence: "0.982",
        model: "claude-sonnet-4-6",
        quality: "0.94",
        escalated: "false",
        confidenceColor: "text-success",
        qualityColor: "text-success",
        escalatedColor: "text-warning"
      });
      setIsGlitching(false);
    }
  }, [isSimulatingFallback]);

  const ontologyRules = [
    { name: 'Orchestrator Agent', desc: 'Claude Sonnet reads every agent heartbeat, detects cross-agent patterns, issues corrections.', status: 'Sonnet' },
    { name: 'Confidence Threshold Gate', desc: 'Deterministic quality scoring (0.0–1.0). Auto-executes when safe, escalates to human when uncertain.', status: 'Active' },
    { name: 'Human Escalation Protocol', desc: 'If confidence < 0.4 or impact > $500k, action is held for human approval. Full audit trail either way.', status: 'Strict' },
  ];

  return (
    <section id="platform" className="py-24 border-b border-black/5 bg-paper relative overflow-hidden noise-texture">
      <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center relative z-10">

        {/* Left Concept */}
        <div>
          <h2 className="text-3xl lg:text-5xl font-semibold tracking-tight text-ink mb-6">
            13 agents. One orchestrator. Zero gaps.
          </h2>
          <p className="text-steel text-lg font-light leading-relaxed mb-8">
            Every agent runs on its own schedule, self-heals on failure, and escalates only when genuinely needed. The Orchestrator reads every heartbeat, detects cross-agent patterns using deepagents, and issues corrections — all without human involvement.
          </p>

          <div className="space-y-4">
            {ontologyRules.map((rule, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, x: -20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ delay: idx * 0.1, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="flex items-center justify-between p-4 rounded-xl border border-black/5 bg-surface liquid-glass group cursor-pointer"
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
            href="https://github.com/ujjwalredd/Supply-Chain/tree/main/agents"
            target="_blank"
            rel="noopener noreferrer"
            className="mt-8 inline-flex items-center gap-2 text-sm text-ink font-medium hover:text-accent transition-colors"
          >
            View All 13 Agents on GitHub <ArrowRight size={16} />
          </a>
        </div>

        {/* Right: Holographic AI Terminal */}
        <motion.div
          ref={terminalRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          initial={{ opacity: 0, y: 40, scale: 0.98 }}
          whileInView={{ opacity: 1, y: 0, scale: 1 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
          animate={{
            rotateY: mousePos.x * 8,
            rotateX: mousePos.y * -6,
          }}
          style={{
            perspective: 1200,
            transformStyle: "preserve-3d",
          }}
          className="relative lg:ml-8"
        >
          {/* Ambient glow behind terminal */}
          <div className={`absolute inset-0 blur-[100px] rounded-full pointer-events-none transition-all duration-700 ${isSimulatingFallback ? 'bg-purple-500/10 scale-110' : 'bg-accent/5'}`} />

          {/* Holographic Terminal Card */}
          <div className={`liquid-glass rounded-[20px] overflow-hidden relative z-10 shadow-2xl transition-all duration-500 ${isGlitching ? 'glitch-active' : ''} ${isSimulatingFallback ? 'border-purple-400/30' : 'border-black/10'}`}
            style={{
              transform: `translateZ(30px)`,
            }}
          >
            {/* Scanning laser line */}
            <div className={`scanning-laser ${isSimulatingFallback ? 'scanning-laser--crisis' : ''}`} />

            {/* Mac OS style window header */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-black/5 bg-surface/80 backdrop-blur-sm">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-red-400" />
                <div className="w-3 h-3 rounded-full bg-amber-400" />
                <div className="w-3 h-3 rounded-full bg-emerald-400" />
              </div>
              <div className="ml-4 text-[10px] font-mono font-medium text-steel">analysis_result.json</div>
              {isSimulatingFallback && (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="ml-auto text-[9px] font-mono font-bold text-warning bg-warning/10 px-2 py-0.5 rounded-full"
                >
                  ⚡ ESCALATED TO HUMAN
                </motion.div>
              )}
            </div>

            {/* JSON Code with glitch overlay */}
            <div className={`p-6 font-mono text-xs sm:text-sm text-steel leading-relaxed overflow-x-auto transition-colors duration-500 ${isSimulatingFallback ? 'bg-purple-50/50' : 'bg-[#FAFAFA]'}`}>
              {/* Chromatic aberration layers during glitch */}
              {isGlitching && (
                <>
                  <div className="absolute inset-0 bg-red-500/[0.03] mix-blend-multiply z-20 pointer-events-none" style={{ transform: 'translate(-2px, 1px)' }} />
                  <div className="absolute inset-0 bg-blue-500/[0.03] mix-blend-multiply z-20 pointer-events-none" style={{ transform: 'translate(2px, -1px)' }} />
                </>
              )}

              <span className="text-ink">{'{'}</span><br />
              <span className="ml-4 text-ink font-semibold">"deviation_id"</span>: <span className="text-accent">"DEV-092A"</span>,<br />
              <span className="ml-4 text-ink font-semibold">"root_cause_analysis"</span>: <span className="text-ink">{'{'}</span><br />
              <span className="ml-8 text-ink font-semibold">"primary_factor"</span>: <span className="text-accent">"Vessel congested{isSimulatingFallback ? " — HIGH UNCERTAINTY" : ""}"</span>,<br />
              <span className="ml-8 text-ink font-semibold">"confidence_score"</span>: <motion.span key={displayData.confidence} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ type: "spring", bounce: 0.4 }} className={displayData.confidenceColor}>{displayData.confidence}</motion.span><br />
              <span className="ml-4 text-ink">{'}'}</span>,<br />
              <span className="ml-4 text-ink font-semibold">"financial_impact"</span>: <span className="text-ink">{'{'}</span><br />
              <span className="ml-8 text-ink font-semibold">"computed_loss_usd"</span>: <span className="text-warning">2400000</span>,<br />
              <span className="ml-8 text-ink font-semibold">"penalty_risk"</span>: <span className="text-danger">"CRITICAL"</span><br />
              <span className="ml-4 text-ink">{'}'}</span>,<br />
              <span className="ml-4 text-ink font-semibold">"model_used"</span>: <motion.span key={displayData.model} initial={{ opacity: 0, scale: 0.8, filter: "blur(4px)" }} animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }} transition={{ type: "spring", bounce: 0.3 }} className="text-accent">"{displayData.model}"</motion.span>,<br />
              <span className="ml-4 text-ink font-semibold">"quality_score"</span>: <motion.span key={displayData.quality} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ type: "spring", bounce: 0.4 }} className={displayData.qualityColor}>{displayData.quality}</motion.span>,<br />
              <span className="ml-4 text-ink font-semibold">"human_escalated"</span>: <motion.span key={displayData.escalated} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ type: "spring", bounce: 0.4 }} className={displayData.escalatedColor}>{displayData.escalated}</motion.span>,<br />
              <span className="ml-4 text-ink font-semibold">"action_executor"</span>: <span className={isSimulatingFallback ? "text-warning" : "text-success"}>{isSimulatingFallback ? '"ESCALATE_TO_HUMAN"' : '"AUTO_RESOLVED"'}</span><br />
              <span className="text-ink">{'}'}</span>
            </div>
            
            {/* Interactive Toggle Button */}
            <div className={`border-t p-3 flex justify-end transition-colors duration-500 ${isSimulatingFallback ? 'bg-purple-50/30 border-purple-200/30' : 'bg-surface border-black/5'}`}>
              <button 
                onClick={() => setIsSimulatingFallback(!isSimulatingFallback)}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-xs font-semibold transition-all shadow-sm border ${isSimulatingFallback ? 'bg-purple-600 text-white border-transparent hover:bg-purple-700' : 'bg-white text-ink border-black/10 hover:bg-gray-50'}`}
              >
                <RefreshCw size={14} className={isGlitching ? 'animate-spin' : ''} />
                {isSimulatingFallback ? 'Reset — Auto-Resolved' : 'Simulate Low Confidence → Escalate'}
              </button>
            </div>
          </div>

          {/* Floating UI Badges with holographic depth */}
          <motion.div
            animate={{ y: [0, -10, 0] }} transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
            style={{ transform: "translateZ(60px)" }}
            className="absolute -bottom-6 -right-6 flex items-center justify-center w-16 h-16 rounded-2xl bg-white/80 backdrop-blur-lg border border-white/40 shadow-xl z-20"
          >
            <ActivitySquare className="text-accent" size={24} />
          </motion.div>
          <motion.div
            animate={{ y: [0, 8, 0] }} transition={{ repeat: Infinity, duration: 5, ease: "easeInOut", delay: 1 }}
            style={{ transform: "translateZ(50px)" }}
            className="absolute -top-6 -left-6 flex items-center justify-center w-12 h-12 rounded-xl bg-white/80 backdrop-blur-lg border border-white/40 shadow-xl z-20"
          >
            <BrainCircuit className="text-ink" size={20} />
          </motion.div>

        </motion.div>
      </div>
    </section>
  );
}
