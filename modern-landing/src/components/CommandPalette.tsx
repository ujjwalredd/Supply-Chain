import { useEffect, useState } from 'react';
import { Command } from 'cmdk';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Map, Code2, Layers, ArrowRight, X, AlertTriangle } from 'lucide-react';

export function CommandPalette() {
  const [open, setOpen] = useState(false);

  // Toggle the menu when ⌘K is pressed
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };

    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh] sm:pt-[25vh]">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-black/20 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />

          {/* Palette */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="w-full max-w-xl bg-white/90 backdrop-blur-xl rounded-2xl shadow-2xl border border-black/10 overflow-hidden relative z-10 mx-4"
          >
            <Command className="w-full flex flex-col">
              <div className="flex items-center border-b border-black/5 px-4 h-14">
                <Search className="w-5 h-5 text-steel/50 mr-3" />
                <Command.Input 
                  placeholder="Type a command or search..." 
                  className="w-full flex-1 bg-transparent border-none outline-none focus:outline-none focus:ring-0 text-ink text-sm font-medium placeholder:text-steel/50"
                  autoFocus
                />
                <button onClick={() => setOpen(false)} className="text-steel/50 hover:text-ink"><X size={16} /></button>
              </div>

              <Command.List className="max-h-[300px] overflow-y-auto p-2 scrollbar-hide py-3 space-y-1">
                <Command.Empty className="py-6 text-center text-sm text-steel">No results found.</Command.Empty>

                <Command.Group heading={<span className="text-[10px] uppercase font-semibold text-steel/50 px-2 py-1 select-none">Navigation</span>}>
                  <Command.Item 
                    onSelect={() => { setOpen(false); document.getElementById('dashboard')?.scrollIntoView({ behavior: 'smooth' }) }}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-ink aria-selected:bg-subtle aria-selected:text-ink cursor-pointer transition-colors"
                  >
                    <Map size={16} className="text-steel" />
                    <span>Control Tower Dashboard</span>
                    <ArrowRight size={14} className="ml-auto text-steel/30 opacity-0 group-aria-selected:opacity-100" />
                  </Command.Item>
                  <Command.Item 
                    onSelect={() => { setOpen(false); document.getElementById('architecture')?.scrollIntoView({ behavior: 'smooth' }) }}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-ink aria-selected:bg-subtle aria-selected:text-ink cursor-pointer transition-colors"
                  >
                    <Layers size={16} className="text-steel" />
                    <span>View Architecture</span>
                  </Command.Item>
                </Command.Group>

                <div className="h-px bg-black/5 my-2 mx-2" />

                <Command.Group heading={<span className="text-[10px] uppercase font-semibold text-steel/50 px-2 py-1 select-none">Development</span>}>
                  <Command.Item 
                    onSelect={() => { setOpen(false); window.open('https://github.com/ujjwalredd/Supply-Chain', '_blank') }}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-ink aria-selected:bg-subtle aria-selected:text-ink cursor-pointer transition-colors"
                  >
                    <Code2 size={16} className="text-steel" />
                    <span>Review Source Code on GitHub</span>
                  </Command.Item>
                </Command.Group>

                <div className="h-px bg-black/5 my-2 mx-2" />

                <Command.Group heading={<span className="text-[10px] uppercase font-semibold text-steel/50 px-2 py-1 select-none">Simulations</span>}>
                  <Command.Item 
                    onSelect={() => { 
                      setOpen(false); 
                      document.getElementById('dashboard')?.scrollIntoView({ behavior: 'smooth' });
                      setTimeout(() => {
                        window.dispatchEvent(new CustomEvent('simulate-deviation', { detail: 'factory-fire' }));
                      }, 500);
                    }}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-danger aria-selected:bg-danger/5 aria-selected:text-danger-dark cursor-pointer transition-colors"
                  >
                    <AlertTriangle size={16} className="text-danger" />
                    <span>Trigger: Mass Cascading Failure (Shenzhen)</span>
                  </Command.Item>
                </Command.Group>
              </Command.List>

              <div className="p-3 border-t border-black/5 bg-subtle text-[10px] font-medium text-steel flex justify-between items-center">
                <span>Supply Chain Core OS</span>
                <span className="bg-black/5 px-2 py-1 rounded text-ink/70">v7.0.0</span>
              </div>
            </Command>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
