import { motion } from 'framer-motion';
import { Target, Webhook, TrendingUp, Search, Zap, AlertTriangle } from 'lucide-react';

export function Capabilities() {
  const capabilities = [
    {
      title: 'Real-Time Deviation Detection',
      desc: 'Automatic evaluation of anomalies: DELAY (>14d), STOCKOUT (<5 units), or financial ANOMALY via Kafka stream ingestion mapped to PostgreSQL.',
      icon: Search,
    },
    {
      title: 'Supplier Risk Matrix',
      desc: 'Live tracking of dependency percentage and concentration risk per supplier. Computes trust scores dynamically after every deviation.',
      icon: AlertTriangle,
    },
    {
      title: 'Autonomous Execution',
      desc: 'The ActionExecutor subsystem automatically builds execution schemas like REROUTE (finding alternate suppliers with trust ≥ 0.80) or EXPEDITE via automated Slack alerting.',
      icon: Target,
    },
    {
      title: 'Financial Impact Engine',
      desc: 'Pre-computes expected carrying cost, delay cost, and immediate stockout penalties in USD before passing the state matrix to Claude.',
      icon: TrendingUp,
    },
    {
      title: 'Zero-Latency WebSockets',
      desc: 'PostgreSQL row upserts are published directly to Redis, which streams to the Next.js control tower for instant KPI adjustments without manual refresh.',
      icon: Zap,
    },
    {
      title: 'Graph Network Optimization',
      desc: 'Full graph ontology mapping the complex relationships across 19 plants and 11 ports to uncover co-affected downstream orders immediately.',
      icon: Webhook,
    }
  ];

  return (
    <section className="py-24 bg-paper relative z-10 border-b border-black/5">
      <div className="max-w-7xl mx-auto px-6">
        
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="mb-16 max-w-3xl"
        >
          <h2 className="text-sm font-mono text-accent uppercase tracking-widest mb-4 font-semibold">Technical Capabilities</h2>
          <h3 className="text-3xl lg:text-4xl font-semibold tracking-tight text-ink mb-6">
            A comprehensive suite of supply chain intelligence built on a medallion data lakes.
          </h3>
          <p className="text-steel text-lg font-light leading-relaxed mb-8">
            The platform replicates the end-to-end architecture of a $100M+ enterprise operations tower. 
            By connecting raw data pipelines directly to deterministic AI agents, we execute decisions the moment a signal drops.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-12">
          {capabilities.map((cap, i) => {
            const Icon = cap.icon;
            return (
              <motion.div 
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ delay: i * 0.1, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="flex flex-col group"
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-subtle border border-black/5 group-hover:bg-white group-hover:shadow-sm group-hover:border-black/10 transition-all">
                    <Icon size={18} className="text-ink" />
                  </div>
                  <h4 className="text-ink font-semibold">{cap.title}</h4>
                </div>
                <p className="text-steel text-sm leading-relaxed">{cap.desc}</p>
              </motion.div>
            );
          })}
        </div>

      </div>
    </section>
  );
}
