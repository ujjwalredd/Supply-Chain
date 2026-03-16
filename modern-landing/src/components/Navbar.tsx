import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Menu, X } from 'lucide-react';

// Shared event so CommandPalette can listen without synthetic keyboard hacks
export const openCommandPalette = () =>
  window.dispatchEvent(new CustomEvent('fa:open-command-palette'));

const NAV_LINKS = [
  { href: '#platform',       label: 'Agents' },
  { href: '#dashboard',      label: 'Control Tower' },
  { href: '#architecture',   label: 'Architecture' },
  { href: '#design-partner', label: 'Design Partner' },
];

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Close menu on resize to desktop
  useEffect(() => {
    const onResize = () => { if (window.innerWidth >= 768) setMenuOpen(false); };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  return (
    <>
      <motion.header
        initial={{ y: -80, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 border-b ${
          scrolled || menuOpen
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

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-8 text-xs font-medium text-steel">
            {NAV_LINKS.map(({ href, label }) => (
              <a key={href} href={href} className="hover:text-ink transition-colors">{label}</a>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <button
              onClick={openCommandPalette}
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
              className="hidden sm:flex items-center gap-2 bg-ink text-paper px-4 py-1.5 rounded-lg hover:bg-black transition-colors font-semibold text-xs shadow-sm h-8"
            >
              View on GitHub
            </a>
            {/* Mobile hamburger */}
            <button
              onClick={() => setMenuOpen(o => !o)}
              className="md:hidden flex items-center justify-center w-8 h-8 rounded-lg border border-black/8 hover:bg-subtle/60 transition-colors text-ink"
              aria-label="Toggle menu"
            >
              {menuOpen ? <X size={16} /> : <Menu size={16} />}
            </button>
          </div>
        </div>

        {/* Mobile drawer */}
        <AnimatePresence>
          {menuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              className="md:hidden overflow-hidden border-t border-black/5 bg-white/95 backdrop-blur-xl"
            >
              <nav className="flex flex-col px-6 py-4 gap-1">
                {NAV_LINKS.map(({ href, label }) => (
                  <a
                    key={href}
                    href={href}
                    onClick={() => setMenuOpen(false)}
                    className="text-sm font-medium text-steel hover:text-ink transition-colors py-2.5 border-b border-black/4 last:border-0"
                  >
                    {label}
                  </a>
                ))}
                <a
                  href="https://github.com/ujjwalredd/Supply-Chain"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => setMenuOpen(false)}
                  className="mt-3 flex items-center justify-center gap-2 bg-ink text-paper px-4 py-2.5 rounded-lg hover:bg-black transition-colors font-semibold text-sm"
                >
                  View on GitHub
                </a>
              </nav>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.header>
    </>
  );
}
