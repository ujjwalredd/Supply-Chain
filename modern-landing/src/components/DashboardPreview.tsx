import { useState, useRef, useEffect } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import { ChevronRight, Cpu, CheckCircle2, AlertTriangle } from 'lucide-react';
import { AnimatedNumber, AnimatedDecimal } from './AnimatedNumber';
import { TiltCard } from './TiltCard';
import { CobeGlobe } from './CobeGlobe';
import { QueryBox } from './QueryBox';

const staggerItem = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.8, ease: [0.16, 1, 0.3, 1] as any } }
};

export function DashboardPreview() {
  const [activeTab, setActiveTab] = useState('Overview');
  const [isMapExpanded, setIsMapExpanded] = useState(false);
  const [isCrisis, setIsCrisis] = useState(false);

  useEffect(() => {
    const handleCrisis = (e: any) => {
      if (e.detail === 'factory-fire') {
        setIsCrisis(true);
        setActiveTab('Overview');
      }
    };
    window.addEventListener('simulate-deviation', handleCrisis);
    return () => window.removeEventListener('simulate-deviation', handleCrisis);
  }, []);
  
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start 95%", "start 10%"]
  });

  const rotateX = useTransform(scrollYProgress, [0, 1], [25, 0]);
  const scale = useTransform(scrollYProgress, [0, 1], [0.85, 1]);
  const opacity = useTransform(scrollYProgress, [0, 1], [0.3, 1]);
  const y = useTransform(scrollYProgress, [0, 1], [120, 0]);

  return (
    <section id="dashboard" className="py-24 relative z-10 bg-surface border-y border-black/5 noise-texture overflow-hidden" style={{ perspective: "2000px" }}>
      {/* Dynamic Ambient Backlight — health-reactive */}
      <div className={`ambient-glow ${isCrisis ? 'ambient-glow--crisis' : 'ambient-glow--stable'}`} />

      <div className="max-w-[1400px] mx-auto px-6 relative z-10">
        
        <motion.div 
          initial="hidden" whileInView="visible" viewport={{ once: true, margin: '-100px' }}
          variants={{ visible: { transition: { staggerChildren: 0.1 } } }}
          className="mb-12 flex items-end justify-between"
        >
          <motion.div variants={staggerItem}>
            <h2 className="text-sm font-mono text-accent mb-2 uppercase tracking-widest font-semibold">Control Tower</h2>
            <h3 className="text-3xl font-semibold tracking-tight text-ink">Real-Time Operations Terminal</h3>
          </motion.div>
          <motion.div variants={staggerItem} className="hidden md:flex text-xs font-mono text-steel items-center gap-4">
            <span className={`flex items-center gap-1.5 transition-colors duration-700 ${isCrisis ? 'text-danger' : ''}`}>
              <div className={`w-2 h-2 rounded-full transition-colors duration-700 ${isCrisis ? 'bg-danger animate-pulse' : 'bg-success'}`}/>
              {isCrisis ? 'Kafka Pipeline: OVERFLOW' : 'Kafka Pipeline: Synced'}
            </span>
            <span className={`flex items-center gap-1.5 transition-colors duration-700 ${isCrisis ? 'text-danger' : ''}`}>
              <div className={`w-2 h-2 rounded-full transition-colors duration-700 ${isCrisis ? 'bg-danger animate-pulse' : 'bg-success'}`}/>
              {isCrisis ? 'Dagster Medallion: STALE' : 'Dagster Medallion: Fresh'}
            </span>
          </motion.div>
        </motion.div>

        {/* Dashboard Frame */}
        <motion.div 
          ref={containerRef}
          style={{
            rotateX,
            scale,
            opacity,
            y,
            transformOrigin: "bottom center",
            transformPerspective: 2000,
            boxShadow: isCrisis 
              ? "0 25px 60px -12px rgba(239, 68, 68, 0.35), 0 0 80px -20px rgba(239, 68, 68, 0.15)"
              : "0 25px 50px -12px rgba(0, 0, 0, 0.25)"
          }}
          className={`glass-card overflow-hidden bg-white flex flex-col relative transition-shadow duration-1000 ${isCrisis ? 'border-danger/30' : ''}`}
        >
          
          {/* Dashboard Header Menu */}
          <div className="h-12 border-b border-black/5 bg-surface/50 flex px-2 sm:px-6 justify-between items-center relative z-20">
            <div className="flex text-xs font-medium text-steel h-full">
              {['Overview', 'AI Copilot', 'Orders', 'Network Map'].map((tab) => (
                <button 
                  key={tab}
                  onClick={(e) => {
                    e.preventDefault();
                    setActiveTab(tab);
                    if (tab !== 'Network Map') setIsMapExpanded(false);
                  }}
                  className={`h-full px-4 sm:px-6 flex items-center transition-colors duration-300 relative ${activeTab === tab ? 'text-ink' : 'hover:text-ink'}`}
                >
                  {tab}
                  {activeTab === tab && (
                    <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-ink" />
                  )}
                </button>
              ))}
            </div>
            <div className="hidden sm:flex gap-2 text-[10px] font-mono shrink-0">
              <span className="px-2 py-1 bg-white border border-black/5 rounded text-steel">User: OpsLead</span>
              <span className="px-2 py-1 bg-white border border-black/5 rounded text-steel">Env: PRD</span>
            </div>
          </div>

          <div className="p-6 h-full relative bg-subtle/30 overflow-y-auto max-h-[600px] min-h-[500px]">
            
            {activeTab === 'Overview' && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="grid grid-cols-12 gap-6 h-full">
                {/* Left Column (KPIs & Alerts) */}
                <div className="col-span-12 lg:col-span-8 flex flex-col gap-6">
                  
                  {/* KPIs */}
                  <div className="grid grid-cols-3 gap-6">
                    <motion.div 
                      initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1, duration: 0.5, ease: [0.16,1,0.3,1] }}
                    >
                      <TiltCard className="p-5 rounded-xl border bg-white shadow-sm border-black/5 h-full">
                        <div className="text-xs text-steel font-medium mb-1">Pipeline Value</div>
                        <div className="text-2xl font-semibold tracking-tight text-ink">$<AnimatedDecimal value={84.2} />M</div>
                        <div className="text-[10px] mt-2 font-medium text-steel">+1.2% this week</div>
                      </TiltCard>
                    </motion.div>
                    
                    <motion.div 
                      initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.5, ease: [0.16,1,0.3,1] }}
                    >
                      <TiltCard className="p-5 rounded-xl border bg-white shadow-sm border-black/5 h-full">
                        <div className="text-xs text-steel font-medium mb-1">Avg Resolution Time</div>
                        <div className="text-2xl font-semibold tracking-tight text-ink"><AnimatedDecimal value={0.1} />s</div>
                        <div className="text-[10px] mt-2 font-medium text-steel">vs 48hrs manual</div>
                      </TiltCard>
                    </motion.div>
                    
                    <motion.div 
                      initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.5, ease: [0.16,1,0.3,1] }}
                    >
                      <TiltCard className={`p-5 rounded-xl border bg-white shadow-sm h-full transition-colors duration-500 ${isCrisis ? 'border-danger bg-danger/5' : 'border-danger/30'}`}>
                        <div className="text-xs text-steel font-medium mb-1">Critical Deviations</div>
                        <div className="text-2xl font-semibold tracking-tight text-danger">
                          <AnimatedNumber value={isCrisis ? 124 : 3} />
                        </div>
                        <div className={`text-[10px] mt-2 font-medium ${isCrisis ? 'text-danger font-bold animate-pulse' : 'text-danger/80'}`}>
                          {isCrisis ? 'SYSTEM OVERLOAD: MASS CASCADING FAILURE' : 'Requires Review'}
                        </div>
                      </TiltCard>
                    </motion.div>
                  </div>

                  {/* Main Chart / Heatmap Space */}
                  <div className="flex-1 grid grid-cols-2 gap-6">
                    <motion.div 
                      initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2, duration: 0.6 }}
                      className="bg-white p-5 rounded-xl border border-black/5 shadow-sm min-h-[300px] flex flex-col"
                    >
                      <div className="text-xs font-semibold text-ink mb-4 flex justify-between">
                        <span>Supplier Trust Heatmap</span>
                        <span className="text-steel font-normal">Max Dev: 14%</span>
                      </div>
                      <div className="flex-1 grid grid-cols-8 grid-rows-6 gap-1.5 relative">
                        {Array.from({length: 48}).map((_, i) => (
                          <div key={i} className={`rounded-[3px] transition-colors duration-500 ${
                            i === 12 || i === 23 ? 'bg-danger/80 shadow-sm' : 
                            Math.random() > 0.8 ? 'bg-accent/20' : 
                            Math.random() > 0.5 ? 'bg-black/5' : 'bg-black/[0.02]'
                          }`} />
                        ))}
                        {/* Tooltip Mock */}
                        <div className="absolute top-1/4 left-1/4 translate-x-4 bg-white border border-black/10 text-xs p-3 rounded-lg shadow-xl z-10 w-40 hidden lg:block">
                          <div className="font-semibold text-ink">GlobalFreight</div>
                          <div className="text-danger mt-1 font-medium">Trust Score: 64%</div>
                          <div className="text-steel mt-1 leading-tight">Dependency Cap Breached</div>
                        </div>
                      </div>
                    </motion.div>

                    <motion.div 
                      initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3, duration: 0.6 }}
                      className="bg-white p-5 rounded-xl border border-black/5 shadow-sm flex flex-col h-full"
                    >
                      <div className="text-xs font-semibold text-ink mb-4 flex justify-between">
                        <span>Deviation Log</span>
                        {isCrisis && <span className="text-danger flex items-center gap-1 animate-pulse"><AlertTriangle size={12}/> CRISIS</span>}
                      </div>
                      <div className="space-y-3">
                        {(isCrisis ? [
                          { type: 'FACTORY_FIRE', entity: 'Shenzhen Hub', risk: 'CRITICAL', riskColor: 'bg-danger animate-pulse', time: 'Just now' },
                          { type: 'DISRUPTED', entity: 'Ocean Line 4', risk: 'CRITICAL', riskColor: 'bg-danger', time: '1m ago' },
                          { type: 'REROUTE', entity: 'Air Fght 22', risk: 'HIGH', riskColor: 'bg-warning', time: '1m ago' },
                        ] : [
                          { type: 'DELAY', entity: 'Ocean Line 4', risk: 'HIGH', riskColor: 'bg-danger', time: '1m ago' },
                          { type: 'STOCKOUT', entity: 'WH-East', risk: 'MED', riskColor: 'bg-warning', time: '12m ago' },
                          { type: 'ANOMALY', entity: 'Supplier Z', risk: 'LOW', riskColor: 'bg-steel', time: '1h ago' },
                        ]).map((alert, i) => (
                          <div key={i} className={`flex items-center justify-between p-3 rounded-lg border text-xs transition-colors cursor-pointer ${isCrisis && i === 0 ? 'bg-danger/10 border-danger/20 hover:bg-danger/20' : 'bg-subtle border-black/5 hover:bg-black/5'}`}>
                            <div className="flex items-center gap-2.5">
                              <div className={`w-2 h-2 rounded-full shadow-sm ${alert.riskColor}`} />
                              <span className={`font-mono font-medium ${isCrisis && i === 0 ? 'text-danger' : 'text-ink'}`}>{alert.type}</span>
                            </div>
                            <span className={isCrisis && i === 0 ? 'text-danger-dark font-semibold' : 'text-steel'}>{alert.entity}</span>
                            <span className="text-[10px] text-steel font-medium">{alert.time}</span>
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  </div>
                </div>

                {/* Right Column (AI Panel Mock) */}
                <motion.div 
                  initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.4, duration: 0.6, ease: [0.16,1,0.3,1] }}
                  className="col-span-12 lg:col-span-4 bg-white rounded-xl border border-black/5 shadow-card p-5 flex flex-col relative overflow-hidden"
                >
                  <div className="absolute top-0 right-0 w-32 h-32 bg-accent/5 rounded-bl-[100px] pointer-events-none" />
                  
                  <div className="flex items-center justify-between border-b border-black/5 pb-4 mb-4 relative z-10">
                    <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                      <Cpu className="text-accent" size={16} />
                      <span>AI Reasoning</span>
                    </div>
                    <div className="text-[10px] font-semibold tracking-wide bg-accent/10 text-accent px-2 py-0.5 rounded border border-accent/20">ACTIVE</div>
                  </div>

                  <div className="flex-1 flex flex-col gap-4 text-sm text-steel mb-4 relative z-10">
                    <p>Analyzing deviation: <span className="text-ink font-mono font-medium">{isCrisis ? 'DEV-991A' : 'DEV-4922'}</span>.</p>
                    <div className={`flex items-start gap-2 p-4 rounded-lg border font-mono shadow-inner ${isCrisis ? 'bg-danger/5 border-danger/20 text-xs' : 'bg-subtle border-black/5 text-xs'}`}>
                      <span className={isCrisis ? 'text-danger font-bold' : 'text-accent font-bold'}>{'>'}</span>
                      <span className={isCrisis ? 'leading-relaxed text-danger-dark font-medium' : 'leading-relaxed text-ink/80'}>
                        {isCrisis ? (
                          <>
                            [CRITICAL] Factory fire detected at Tier-1 Assembly in Shenzhen. Immediate capacity loss of 40,000 units/day.<br /><br />
                            Spiking alternative node "Vietnam-Hub-2" capacity...<br />
                            Activating emergency air freight ($450k overhead).<br />
                            Awaiting operator confirmation for 14 downstream reroutes.
                          </>
                        ) : (
                          <>
                            Port congestion detected at Shanghai.<br/>
                            Delay: <span className="font-semibold text-ink">14 Days</span>.<br/>
                            Carrying Cost Impact: <span className="text-warning font-semibold">$240,000</span>.<br/>
                            Stockout Penalty: <span className="text-danger font-semibold">$2.4M</span>.
                          </>
                        )}
                      </span>
                    </div>
                    
                    <div className="mt-2">
                      <span className="text-[10px] font-semibold text-steel uppercase tracking-widest mb-2 block">Available Actions (3)</span>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between bg-white border border-accent/30 shadow-sm p-3 rounded-lg cursor-pointer hover:border-accent transition-colors relative overflow-hidden group">
                          <div className="absolute inset-0 bg-accent/5 translate-x-[-100%] group-hover:translate-x-0 transition-transform duration-500 ease-out" />
                          <div className="flex flex-col relative z-10">
                            <span className="text-ink text-xs font-semibold">REROUTE</span>
                            <span className="text-[10px] text-steel">Alt Supplier (Trust ≥ 0.80)</span>
                          </div>
                          <ChevronRight size={16} className="text-accent relative z-10" />
                        </div>
                        <div className="flex items-center justify-between bg-white border border-black/5 p-3 rounded-lg cursor-pointer hover:bg-subtle transition-colors opacity-70">
                          <div className="flex flex-col">
                            <span className="text-ink text-xs font-medium">EXPEDITE</span>
                            <span className="text-[10px] text-steel">Air Freight (Cost: $85k)</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-auto pt-4 relative z-10">
                    <button className="w-full bg-ink text-paper font-semibold text-xs py-3 rounded-lg flex items-center justify-center gap-2 hover:bg-black transition-all shadow-md hover:shadow-lg hover:-translate-y-0.5 duration-300">
                      <CheckCircle2 size={16} /> Execute Reroute Option
                    </button>
                  </div>
                </motion.div>
              </motion.div>
            )}

            {activeTab === 'Orders' && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="bg-white rounded-xl border border-black/5 shadow-sm overflow-hidden h-full flex flex-col">
                <div className="px-6 py-4 border-b border-black/5 flex justify-between items-center bg-surface">
                  <span className="text-sm font-semibold text-ink">Live Order Fulfillment Stream</span>
                  <div className="flex gap-2">
                    <span className="px-2 py-1 bg-white border border-black/5 rounded text-[10px] text-steel font-mono">Total: 4,204</span>
                    <span className="px-2 py-1 bg-danger/10 border border-danger/20 rounded text-[10px] text-danger font-mono font-semibold">Delayed: 12</span>
                  </div>
                </div>
                <div className="flex-1 overflow-auto p-0">
                  <table className="w-full text-xs text-left">
                    <thead className="text-[10px] text-steel uppercase bg-subtle sticky top-0">
                      <tr>
                        <th className="px-6 py-3 font-medium">Order ID</th>
                        <th className="px-6 py-3 font-medium">Material</th>
                        <th className="px-6 py-3 font-medium">Origin</th>
                        <th className="px-6 py-3 font-medium">Destination</th>
                        <th className="px-6 py-3 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-black/5 text-ink">
                      {[
                        { id: 'ORD-9921', mat: 'Semiconductors', ori: 'Taipei, TW', dest: 'Austin, TX', stat: 'IN TRANSIT', statColor: 'text-accent' },
                        { id: 'ORD-9922', mat: 'Lithium Cells', ori: 'Shenzhen, CN', dest: 'Berlin, DE', stat: 'DELAYED', statColor: 'text-danger font-semibold' },
                        { id: 'ORD-9923', mat: 'Steel Chassis', ori: 'Monterrey, MX', dest: 'Detroit, MI', stat: 'FULFILLED', statColor: 'text-success' },
                        { id: 'ORD-9924', mat: 'Wiring Harness', ori: 'Mumbai, IN', dest: 'Austin, TX', stat: 'PROCESSING', statColor: 'text-steel' },
                        { id: 'ORD-9925', mat: 'Glass Panels', ori: 'Seoul, KR', dest: 'Berlin, DE', stat: 'IN TRANSIT', statColor: 'text-accent' },
                      ].map((row, i) => (
                        <tr key={i} className="hover:bg-subtle transition-colors">
                          <td className="px-6 py-4 font-mono">{row.id}</td>
                          <td className="px-6 py-4">{row.mat}</td>
                          <td className="px-6 py-4 text-steel">{row.ori}</td>
                          <td className="px-6 py-4 text-steel">{row.dest}</td>
                          <td className={`px-6 py-4 ${row.statColor}`}>{row.stat}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}

            {activeTab === 'AI Copilot' && (
              <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} className="h-full">
                <QueryBox />
              </motion.div>
            )}

            {activeTab === 'Network Map' && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="bg-white rounded-xl border border-black/5 shadow-sm overflow-hidden h-full flex flex-col relative">
                
                {!isMapExpanded ? (
                  <div className="p-0 flex-1 flex flex-col items-center justify-center relative overflow-hidden min-h-[600px]">
                    <div className="absolute inset-0 bg-subtle-grid [background-size:24px_24px] pointer-events-none opacity-50" />
                    
                    {/* The 3D Globe */}
                    <div className="absolute inset-0 z-0 opacity-40 flex flex-col items-center justify-center pointer-events-none mt-12">
                      <CobeGlobe />
                    </div>

                    {/* Overlay Content */}
                    <div className="relative z-10 flex flex-col items-center mt-32 pointer-events-auto">
                      <h4 className="text-ink font-semibold mb-2 bg-white/80 backdrop-blur-md px-4 py-1 rounded-full border border-black/5 shadow-sm text-sm">Global Logistics Graph Active</h4>
                    <p className="text-steel text-sm text-center max-w-sm relative z-10 font-light bg-white/80 backdrop-blur-md rounded-xl p-2">
                      Live multi-echelon network topology mapping 19 factories, 11 ports, and 300+ transit lanes using PostgreSQL recursive CTEs.
                    </p>
                    <button 
                      onClick={() => setIsMapExpanded(true)}
                      className="mt-6 border border-black/10 bg-white px-4 py-2 text-xs font-semibold rounded-lg hover:bg-subtle transition-colors shadow-sm relative z-10"
                    >
                      Expand Map View
                    </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col h-full w-full">
                    {/* Global Header for Expanded Map */}
                    <div className="border-b border-black/5 bg-white px-6 py-3 flex justify-between items-center shrink-0">
                      <div className="text-xs font-medium text-ink flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-accent animate-pulse" />
                        Live Topology: <span className="text-accent font-semibold">19 Nodes / 312 Edges</span>
                      </div>
                      <button 
                        onClick={() => setIsMapExpanded(false)}
                        className="text-[10px] font-semibold tracking-wider uppercase text-steel hover:text-ink transition-colors border border-black/5 px-4 py-1.5 rounded bg-subtle hover:bg-black/5"
                      >
                        Close Map
                      </button>
                    </div>

                    <div className="flex flex-1 overflow-hidden">
                      {/* Map Area */}
                      <div className="flex-1 relative bg-surface overflow-hidden p-6 flex flex-col justify-center">
                        <div className="absolute inset-0 bg-subtle-grid [background-size:32px_32px] pointer-events-none opacity-50" />

                      {/* Mock Graph Simulation */}
                      <div className="relative w-full h-[400px] border border-black/5 rounded-xl bg-white shadow-inner flex items-center justify-center overflow-hidden">
                        <svg viewBox="0 0 1000 400" className="w-full h-full drop-shadow-sm min-w-[600px]" preserveAspectRatio="xMidYMid meet">
                          
                          {/* Grid/Background */}
                          <defs>
                            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#f0f0f0" strokeWidth="1"/>
                            </pattern>
                            
                            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                                <feGaussianBlur stdDeviation="4" result="blur" />
                                <feComposite in="SourceGraphic" in2="blur" operator="over" />
                            </filter>
                          </defs>
                          <rect width="100%" height="100%" fill="url(#grid)" />

                          {/* Base Connections */}
                          <g stroke="#E4E4E7" strokeWidth="2" fill="none" className="opacity-80">
                            {/* Path 1 */}
                            <path d="M 120,250 C 200,250 250,140 320,140" strokeDasharray="6 6" />
                            <path d="M 120,250 C 200,250 350,320 450,280" strokeDasharray="6 6" />
                            
                            {/* Path 2 */}
                            <path d="M 320,140 C 400,140 400,100 500,100" />
                            <path d="M 450,280 C 500,280 500,100 500,100" stroke="#EF4444" strokeWidth="2.5" />
                            
                            {/* Path 3 */}
                            <path d="M 500,100 C 600,100 650,200 750,200" stroke="#0070F3" strokeWidth="2.5" />
                            
                            {/* Path 4 */}
                            <path d="M 750,200 C 800,200 850,120 900,120" strokeDasharray="6 6" />
                            <path d="M 750,200 C 800,200 820,300 880,300" strokeDasharray="6 6" />
                          </g>

                          {/* Nodes */}
                          <g>
                            {/* Shenzhen */}
                            <g transform="translate(120, 250)">
                              <circle r="12" fill="#DCFCE7" stroke="#22C55E" strokeWidth="1.5" />
                              <circle r="5" fill="#22C55E" />
                              <rect x="-35" y="20" width="70" height="20" rx="4" fill="white" stroke="#E4E4E7" strokeWidth="1" />
                              <text y="33" textAnchor="middle" className="text-[10px] font-mono font-medium fill-slate-600">Shenzhen</text>
                            </g>

                            {/* Taipei Hub */}
                            <g transform="translate(320, 140)">
                              <circle r="16" fill="#DBEAFE" stroke="#3B82F6" strokeWidth="2" opacity="0.4" />
                              <circle r="12" fill="#DBEAFE" stroke="#3B82F6" strokeWidth="1.5" />
                              <circle r="5" fill="#3B82F6" />
                              <rect x="-40" y="24" width="80" height="22" rx="4" fill="white" stroke="#3B82F6" strokeWidth="1" />
                              <text y="38" textAnchor="middle" className="text-[10px] font-mono font-bold fill-slate-800">Taipei Hub</text>
                            </g>

                            {/* Shanghai DEV (Critical) */}
                            <g transform="translate(450, 280)">
                              <circle r="22" fill="#FEE2E2" opacity="0.5" />
                              <circle r="14" fill="#FEE2E2" stroke="#EF4444" strokeWidth="2" filter="url(#glow)" />
                              <circle r="6" fill="#EF4444" />
                              <rect x="-50" y="26" width="100" height="24" rx="4" fill="#EF4444" />
                              <text y="42" textAnchor="middle" className="text-[11px] font-mono font-bold fill-white">Shanghai DEV</text>
                            </g>

                            {/* Tokyo */}
                            <g transform="translate(500, 100)">
                              <circle r="10" fill="#F4F4F5" stroke="#71717A" strokeWidth="1.5" />
                              <circle r="4" fill="#71717A" />
                              <rect x="-30" y="16" width="60" height="20" rx="4" fill="white" stroke="#E4E4E7" strokeWidth="1" />
                              <text y="29" textAnchor="middle" className="text-[10px] font-mono font-medium fill-slate-600">Tokyo</text>
                            </g>

                            {/* San Fran */}
                            <g transform="translate(750, 200)">
                              <circle r="12" fill="#DCFCE7" stroke="#22C55E" strokeWidth="1.5" />
                              <circle r="5" fill="#22C55E" />
                              <rect x="-35" y="20" width="70" height="20" rx="4" fill="white" stroke="#E4E4E7" strokeWidth="1" />
                              <text y="33" textAnchor="middle" className="text-[10px] font-mono font-medium fill-slate-600">San Fran</text>
                            </g>

                            {/* Berlin */}
                            <g transform="translate(900, 120)">
                              <circle r="10" fill="#DCFCE7" stroke="#22C55E" strokeWidth="1.5" />
                              <circle r="4" fill="#22C55E" />
                              <rect x="-30" y="18" width="60" height="20" rx="4" fill="white" stroke="#E4E4E7" strokeWidth="1" />
                              <text y="31" textAnchor="middle" className="text-[10px] font-mono font-medium fill-slate-600">Berlin</text>
                            </g>
                            
                            {/* Austin */}
                            <g transform="translate(880, 300)">
                              <circle r="10" fill="#DCFCE7" stroke="#22C55E" strokeWidth="1.5" />
                              <circle r="4" fill="#22C55E" />
                              <rect x="-30" y="18" width="60" height="20" rx="4" fill="white" stroke="#E4E4E7" strokeWidth="1" />
                              <text y="31" textAnchor="middle" className="text-[10px] font-mono font-medium fill-slate-600">Austin</text>
                            </g>
                          </g>
                        </svg>
                      </div>
                    </div>

                      {/* Right Panel (Deep dive info) */}
                      <div className="w-68 border-l border-black/5 bg-white p-5 overflow-y-auto flex flex-col relative z-10 shrink-0">
                        <div className="text-xs font-semibold text-ink mb-1">Graph Traversal Logs</div>
                        <div className="text-[10px] text-steel mb-6">Recursive CTE depth: 4 levels</div>

                        <div className="space-y-4">
                          <div className="p-3 bg-danger/5 border border-danger/20 rounded-lg">
                            <div className="text-[10px] text-danger font-semibold mb-1 uppercase tracking-wider">Node Critical</div>
                            <div className="text-xs text-ink font-medium">Shanghai DEV</div>
                            <div className="text-[10px] text-steel mt-2 border-t border-danger/10 pt-2 leading-relaxed">
                              Impacts <span className="text-ink font-semibold">14 edges</span> downstream.<br/>
                              Est. 2-week freeze.
                            </div>
                          </div>

                          <div className="p-3 bg-subtle border border-black/5 rounded-lg">
                            <div className="text-[10px] text-steel font-medium mb-1 uppercase tracking-wider">Alternative Computed</div>
                            <div className="flex items-center gap-2 mt-2">
                              <span className="text-xs font-mono text-ink">Taipei</span>
                              <ChevronRight size={10} className="text-accent" />
                              <span className="text-xs font-mono text-ink">Tokyo</span>
                            </div>
                            <div className="text-[10px] text-success mt-2">+ $140,000 margin preservation</div>
                          </div>

                          <div className="p-3 bg-subtle border border-black/5 rounded-lg">
                            <div className="text-[10px] text-steel font-medium mb-1 uppercase tracking-wider">Supplier Dependency</div>
                            <div className="mt-2 flex flex-col justify-start">
                              <span className="text-xs font-mono text-ink">GlobalFreight</span>
                              <div className="flex items-baseline gap-2 mt-1">
                                <span className="text-sm text-danger font-semibold">34%</span>
                                <span className="font-medium text-steel text-[10px]">(&gt;25% SLA cap)</span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </motion.div>
            )}

            {activeTab === 'Suppliers' && (
              <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {[
                  { name: 'Apex Electronics', tier: 'Tier 1', trust: 0.98, dep: '12%', status: 'Healthy', color: 'bg-success' },
                  { name: 'GlobalFreight Line', tier: 'Logistics', trust: 0.64, dep: '34%', status: 'At Risk', color: 'bg-danger' },
                  { name: 'Norden Steel', tier: 'Tier 2', trust: 0.88, dep: '8%', status: 'Stable', color: 'bg-accent' },
                  { name: 'Pacific Polymers', tier: 'Tier 1', trust: 0.91, dep: '15%', status: 'Healthy', color: 'bg-success' },
                ].map((sup, i) => (
                  <div key={i} className="glass-card bg-white p-5 flex flex-col hover:-translate-y-1 transition-transform duration-300">
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <div className="font-semibold text-ink text-sm">{sup.name}</div>
                        <div className="text-xs text-steel mt-0.5">{sup.tier}</div>
                      </div>
                      <div className={`px-2 py-0.5 rounded text-[10px] font-semibold text-white ${sup.color}`}>
                        {sup.status}
                      </div>
                    </div>
                    <div className="mt-auto space-y-3">
                      <div>
                        <div className="flex justify-between text-[10px] text-steel mb-1">
                          <span>Trust Score</span>
                          <span className="font-mono text-ink">{sup.trust.toFixed(2)}</span>
                        </div>
                        <div className="w-full h-1.5 bg-subtle rounded-full overflow-hidden">
                          <div className={`h-full ${sup.color}`} style={{ width: `${sup.trust * 100}%` }} />
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between text-[10px] text-steel mb-1">
                          <span>Dependency</span>
                          <span className="font-mono text-ink">{sup.dep}</span>
                        </div>
                        <div className="w-full h-1.5 bg-subtle rounded-full overflow-hidden">
                          <div className="h-full bg-steel" style={{ width: sup.dep }} />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </motion.div>
            )}

          </div>
        </motion.div>
      </div>
    </section>
  );
}
