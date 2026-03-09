import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GitBranch, TerminalSquare, Search, Github } from 'lucide-react';

const codeSnippets: Record<string, React.ReactNode> = {
  'engine.py': (
    <>
      <span className="text-gray-400"># Next-Gen Reasoning Engine via Claude Sonnet</span><br />
      <span className="text-accent">def</span> <span className="text-ink font-semibold">analyze_deviation</span>(deviation_id: <span className="text-amber-600">str</span>):<br />
      &nbsp;&nbsp;&nbsp;&nbsp;context = <span className="text-ink font-semibold">fetch_network_context</span>(deviation_id)<br />
      &nbsp;&nbsp;&nbsp;&nbsp;ontology = <span className="text-ink font-semibold">load_business_rules</span>()<br /><br />
      
      &nbsp;&nbsp;&nbsp;&nbsp;<span className="text-gray-400"># Compute financial impact pre-AI</span><br />
      &nbsp;&nbsp;&nbsp;&nbsp;impact = <span className="text-ink font-semibold">calculate_penalty</span>(context.delay_days, context.stock)<br /><br />
      
      &nbsp;&nbsp;&nbsp;&nbsp;<span className="text-accent">return</span> llm.generate(<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;prompt=context,<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;tools=[<span className="text-emerald-600">"REROUTE"</span>, <span className="text-emerald-600">"EXPEDITE"</span>],<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;constraints=ontology<br />
      &nbsp;&nbsp;&nbsp;&nbsp;)
    </>
  ),
  'consumer.py': (
    <>
      <span className="text-gray-400"># Real-time Kafka Event Ingestion</span><br />
      <span className="text-accent">async def</span> <span className="text-ink font-semibold">consume_supplier_events</span>():<br />
      &nbsp;&nbsp;&nbsp;&nbsp;consumer = AIOKafkaConsumer(<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span className="text-emerald-600">'supplier_updates'</span>,<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;bootstrap_servers=<span className="text-emerald-600">'kafka:9092'</span><br />
      &nbsp;&nbsp;&nbsp;&nbsp;)<br />
      &nbsp;&nbsp;&nbsp;&nbsp;<span className="text-accent">await</span> consumer.start()<br /><br />
      &nbsp;&nbsp;&nbsp;&nbsp;<span className="text-accent">try</span>:<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span className="text-accent">async for</span> msg <span className="text-accent">in</span> consumer:<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;event = json.loads(msg.value)<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span className="text-accent">if</span> event[<span className="text-emerald-600">'type'</span>] == <span className="text-emerald-600">'DELAY'</span>:<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span className="text-accent">await</span> <span className="text-ink font-semibold">trigger_deviation_workflow</span>(event)<br />
      &nbsp;&nbsp;&nbsp;&nbsp;<span className="text-accent">finally</span>:<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span className="text-accent">await</span> consumer.stop()
    </>
  ),
  'pg_writer.py': (
    <>
      <span className="text-gray-400"># PostgreSQL Recursive CTE Operations</span><br />
      <span className="text-accent">def</span> <span className="text-ink font-semibold">find_downstream_impact</span>(node_id: <span className="text-amber-600">int</span>):<br />
      &nbsp;&nbsp;&nbsp;&nbsp;query = <span className="text-emerald-600">"""<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;WITH RECURSIVE network AS (<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;SELECT target_id, delay_prop FROM edges WHERE source_id = $1<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;UNION ALL<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;SELECT e.target_id, e.delay_prop + n.delay_prop<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;FROM edges e INNER JOIN network n ON e.source_id = n.target_id<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br />
      &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;SELECT * FROM network WHERE delay_prop &gt; 0.5;<br />
      &nbsp;&nbsp;&nbsp;&nbsp;"""</span><br />
      &nbsp;&nbsp;&nbsp;&nbsp;<span className="text-accent">return</span> db.execute(query, node_id)
    </>
  )
};

export function OpenSourceFeature() {
  const [activeFile, setActiveFile] = useState('engine.py');

  return (
    <section className="py-24 bg-surface border-y border-black/5 relative overflow-hidden">
      <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-accent/5 blur-[120px] rounded-full pointer-events-none -translate-y-1/2 translate-x-1/3" />
      
      <div className="max-w-7xl mx-auto px-6 grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
        
        {/* Left Column: Visual Editor Mock */}
        <motion.div 
          initial={{ opacity: 0, x: -40, filter: 'blur(4px)' }}
          whileInView={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
          className="relative order-2 lg:order-1"
        >
          <div className="glass-card rounded-[20px] bg-white border border-black/10 shadow-2xl relative z-10 flex flex-col overflow-hidden">
            {/* Editor Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-black/5 bg-surface">
              <div className="flex gap-4">
                {['engine.py', 'consumer.py', 'pg_writer.py'].map(file => (
                  <button 
                    key={file}
                    onClick={() => setActiveFile(file)}
                    className={`text-[10px] font-mono transition-colors ${activeFile === file ? 'font-semibold text-ink border-b-2 border-accent pb-[13px] mb-[-14px]' : 'font-medium text-steel hover:text-ink pb-[13px] mb-[-14px] border-b-2 border-transparent'}`}
                  >
                    {file}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-3 text-steel">
                <Search size={14} />
                <GitBranch size={14} />
              </div>
            </div>
            
            {/* Editor Body */}
            <div className="p-6 font-mono text-xs sm:text-sm text-steel leading-relaxed bg-[#FAFAFA] overflow-hidden min-h-[300px] relative">
              {/* AI Scan Line Effect */}
              <motion.div
                className="absolute left-0 right-0 h-16 bg-gradient-to-b from-transparent via-accent/5 to-transparent z-0 pointer-events-none"
                animate={{ y: ['-100%', '300%'] }}
                transition={{
                  duration: 4,
                  repeat: Infinity,
                  ease: "linear"
                }}
              />
              <motion.div
                className="absolute left-0 right-0 h-px bg-accent/20 z-0 pointer-events-none"
                animate={{ y: ['0%', '300%'] }} // Maps to the center of the gradient
                transition={{
                  duration: 4,
                  repeat: Infinity,
                  ease: "linear"
                }}
              />
              <div className="relative z-10 overflow-x-auto" style={{ msOverflowStyle: 'none', scrollbarWidth: 'none' }}>
                <AnimatePresence mode="wait">
                  <motion.div
                    key={activeFile}
                    initial={{ opacity: 0, y: 5 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -5 }}
                    transition={{ duration: 0.2 }}
                  >
                    {codeSnippets[activeFile]}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          </div>
          
          <motion.div 
            animate={{ y: [0, -8, 0] }} transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
            className="absolute -bottom-6 -left-6 flex items-center justify-center w-14 h-14 rounded-2xl bg-ink border border-white/10 shadow-xl z-20 text-white"
          >
            <TerminalSquare size={20} />
          </motion.div>
        </motion.div>

        {/* Right Column: Copy & Link */}
        <div className="order-1 lg:order-2">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          >
            <h2 className="text-sm font-mono text-accent uppercase tracking-widest mb-4 font-semibold">Transparent Development</h2>
            <h3 className="text-3xl lg:text-5xl font-semibold tracking-tight text-ink mb-6">
              Review the entire AI reasoning engine.
            </h3>
            <p className="text-steel text-lg font-light leading-relaxed mb-8">
              Trust is the hardest metric to earn in enterprise supply chains. That’s why we believe in complete transparency. 
              The entire AI operating system—from the Kafka real-time ingestion layer down to the precise `engine.py` logic that handles Claude's structured output—is available to review.
            </p>
            
            <a 
              href="https://github.com/ujjwalredd/Supply-Chain" 
              target="_blank" 
              rel="noopener noreferrer"
            >
              <button className="flex items-center gap-3 bg-ink text-paper px-6 py-3.5 rounded-lg font-medium hover:bg-black transition-all shadow-md hover:shadow-lg hover:-translate-y-0.5 duration-300">
                <Github size={18} /> Deep Dive the GitHub Repo
              </button>
            </a>
          </motion.div>
        </div>

      </div>
    </section>
  );
}
