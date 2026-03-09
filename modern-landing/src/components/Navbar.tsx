import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Activity, Search } from 'lucide-react';

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <motion.header
      initial={{ y: -100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] border-b ${
        scrolled ? 'bg-white/80 backdrop-blur-xl border-black/5 shadow-sm' : 'bg-transparent border-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <button 
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          className="flex items-center gap-2 cursor-pointer transition-transform hover:-translate-y-0.5"
        >
          <Activity className="text-accent" size={18} />
          <span className="font-semibold tracking-wide text-sm text-ink">Adopt</span>
        </button>
        <nav className="hidden md:flex items-center gap-8 text-xs font-medium text-steel">
          <a href="#platform" className="hover:text-ink transition-colors">Platform</a>
          <a href="#dashboard" className="hover:text-ink transition-colors">Control Tower</a>
          <a href="#architecture" className="hover:text-ink transition-colors">Architecture</a>
        </nav>
        <div className="flex items-center gap-4 text-xs font-medium">
          <button 
            onClick={() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-md border border-black/5 hover:bg-subtle/50 transition-colors text-steel h-[32px]"
          >
            <Search size={14} />
            <span className="opacity-80">Search...</span>
            <kbd className="hidden lg:inline-flex items-center gap-1 font-mono text-[10px] bg-black/5 px-1.5 py-0.5 rounded ml-2">
              <span className="text-sm leading-none">⌘</span> K
            </kbd>
          </button>
          
          <a 
            href="https://github.com/ujjwalredd/Supply-Chain" 
            target="_blank" 
            rel="noopener noreferrer"
            className="flex items-center gap-2 bg-ink text-paper px-4 py-1.5 rounded-md hover:bg-black transition-colors font-semibold shadow-sm h-[32px]"
          >
            View Source
          </a>
        </div>
      </div>
    </motion.header>
  );
}
