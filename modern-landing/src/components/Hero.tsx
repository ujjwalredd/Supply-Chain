import { motion } from 'framer-motion';
import { Github } from 'lucide-react';

const smoothTransition = { duration: 1, ease: [0.16, 1, 0.3, 1] as any };

export function Hero() {
  return (
    <section className="relative pt-32 pb-20 md:pt-48 md:pb-32 overflow-hidden">
      {/* Soft Ambient Glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-hero-glow pointer-events-none" />
      
      {/* Very faint background grid */}
      <div className="absolute inset-0 bg-subtle-grid pointer-events-none [background-size:24px_24px] [mask-image:linear-gradient(to_bottom,white,transparent)]" />

      <div className="max-w-7xl mx-auto px-6 flex flex-col items-center text-center relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 15, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ ...smoothTransition, delay: 0 }}
          className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-black/5 bg-white shadow-sm mb-8"
        >
          <div className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          <span className="text-[10px] font-mono tracking-widest text-steel uppercase text-ink">System online · v4.0 Active</span>
        </motion.div>

        <motion.h1 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...smoothTransition, delay: 0.1 }}
          className="text-5xl md:text-[80px] font-semibold tracking-tighter text-gradient mb-8 leading-[1.05] max-w-4xl"
        >
          From signal to execution.<br />Zero latency reasoning.
        </motion.h1>

        <motion.p 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...smoothTransition, delay: 0.2 }}
          className="text-steel text-lg md:text-xl max-w-2xl font-light leading-relaxed mb-10"
        >
          The AI-native supply chain control tower. We don't just detect deviations. 
          We reason through multi-node ontology, forecast financial impact, and execute autonomous reroutes in milliseconds.
        </motion.p>

        <motion.div 
          initial={{ opacity: 0, y: 20, filter: 'blur(4px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{ ...smoothTransition, delay: 0.3 }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4"
        >
          {/* Replaced View Ontology with explicit GitHub Codebase Link */}
          <a 
            href="https://github.com/ujjwalredd/Supply-Chain" 
            target="_blank" 
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 bg-ink text-paper px-6 py-3 rounded-lg font-medium hover:bg-black transition-all duration-300 min-w-[200px] shadow-md hover:shadow-lg hover:-translate-y-0.5"
          >
            <Github size={18} /> View Code on GitHub
          </a>
        </motion.div>

        {/* Integration Ticker */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 0.6 }}
          className="mt-20 md:mt-32 w-full max-w-5xl mx-auto overflow-hidden relative"
        >
          <div className="text-[10px] font-mono font-medium text-steel uppercase tracking-widest mb-6">
            Powered by an Enterprise Data Stack
          </div>
          
          {/* Gradients for fading effect on edges */}
          <div className="absolute left-0 top-10 bottom-0 w-24 bg-gradient-to-r from-paper to-transparent z-10" />
          <div className="absolute right-0 top-10 bottom-0 w-24 bg-gradient-to-l from-paper to-transparent z-10" />
          
          <div className="flex w-[200%] animate-infinite-scroll hover:[animation-play-state:paused] cursor-default">
            {/* First Set */}
            <div className="flex w-1/2 justify-around items-center min-w-max gap-12 sm:gap-20 px-6">
              {['Kafka', 'PostgreSQL', 'Redis', 'Dagster', 'FastAPI', 'MinIO', 'Claude Sonnet', 'Next.js'].map((tech) => (
                <span key={tech} className="text-xl sm:text-2xl font-bold tracking-tight text-ink/20 hover:text-ink/60 transition-colors duration-300">
                  {tech}
                </span>
              ))}
            </div>
            {/* Duplicate Set for smooth infinite loop */}
            <div className="flex w-1/2 justify-around items-center min-w-max gap-12 sm:gap-20 px-6">
              {['Kafka', 'PostgreSQL', 'Redis', 'Dagster', 'FastAPI', 'MinIO', 'Claude Sonnet', 'Next.js'].map((tech) => (
                <span key={`dup-${tech}`} className="text-xl sm:text-2xl font-bold tracking-tight text-ink/20 hover:text-ink/60 transition-colors duration-300">
                  {tech}
                </span>
              ))}
            </div>
          </div>
        </motion.div>

      </div>
    </section>
  );
}
