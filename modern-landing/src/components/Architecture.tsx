import { motion } from 'framer-motion';
import { Database, Zap, Layers, Server } from 'lucide-react';

export function Architecture() {
  const stack = [
    { name: 'Kafka Event Stream', desc: '50+ events/min. Supplier state machines & causality chains.', icon: Zap, color: 'text-warning border-warning/20 bg-warning/5' },
    { name: 'Dagster Pipeline', desc: '14-asset medallion lakehouse. Bronze, Silver, Gold transformations.', icon: Layers, color: 'text-success border-success/20 bg-success/5' },
    { name: 'PostgreSQL Operational', desc: 'Underpinning the state. Real-time deviations & pending actions.', icon: Database, color: 'text-accent border-accent/20 bg-accent/5' },
    { name: 'Next.js App Router', desc: 'Zero-latency WebSocket control tower pushed via Redis Pub/Sub.', icon: Server, color: 'text-ink border-ink/10 bg-surface' },
  ];

  return (
    <section id="architecture" className="py-24 bg-surface">
      <div className="max-w-7xl mx-auto px-6 text-center">
        <motion.div
           initial={{ opacity: 0, y: 20 }}
           whileInView={{ opacity: 1, y: 0 }}
           viewport={{ once: true }}
           transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
          <h2 className="text-sm font-mono text-steel uppercase tracking-widest mb-4 font-semibold">Enterprise Grade Infrastructure</h2>
          <h3 className="text-3xl lg:text-4xl font-semibold tracking-tight text-ink mb-16">
            A modern stack built for scale.<br />No black boxes.
          </h3>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 text-left">
          {stack.map((item, idx) => {
            const Icon = item.icon;
            return (
              <motion.div 
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ delay: idx * 0.1, duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="bg-white p-6 rounded-2xl flex flex-col border border-black/5 shadow-sm hover:shadow-md transition-all duration-500 ease-out hover:-translate-y-1"
              >
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center border mb-6 ${item.color}`}>
                  <Icon size={24} />
                </div>
                <h4 className="text-ink font-semibold mb-2">{item.name}</h4>
                <p className="text-steel text-sm leading-relaxed">{item.desc}</p>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  );
}
