import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Search } from 'lucide-react';

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <motion.header
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 border-b ${
        scrolled
          ? 'bg-white/90 backdrop-blur-xl border-black/5 shadow-sm'
          : 'bg-transparent border-transparent'
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <button
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          className="transition-opacity hover:opacity-70"
        >
          <span className="font-semibold tracking-wide text-sm text-ink">ForeverAutonomous</span>
        </button>

        <nav className="hidden md:flex items-center gap-8 text-xs font-medium text-steel">
          <a href="#platform"       className="hover:text-ink transition-colors">Agents</a>
          <a href="#dashboard"      className="hover:text-ink transition-colors">Control Tower</a>
          <a href="#architecture"   className="hover:text-ink transition-colors">Architecture</a>
          <a href="#design-partner" className="hover:text-ink transition-colors">Design Partner</a>
        </nav>

        <div className="flex items-center gap-3">
          <button
            onClick={() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg border border-black/6 hover:bg-subtle/60 transition-colors text-steel text-xs h-8"
          >
            <Search size={13} />
            <span className="opacity-70">Search</span>
            <kbd className="hidden lg:inline-flex items-center font-mono text-[10px] bg-black/5 px-1.5 py-0.5 rounded ml-1">
              ⌘K
            </kbd>
          </button>
          <a
            href="https://github.com/ujjwalredd/Supply-Chain"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 bg-ink text-paper px-4 py-1.5 rounded-lg hover:bg-black transition-colors font-semibold text-xs shadow-sm h-8"
          >
            View on GitHub
          </a>
        </div>
      </div>
    </motion.header>
  );
}
