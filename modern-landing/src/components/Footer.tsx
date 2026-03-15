import { Github } from 'lucide-react';

export function Footer() {
  return (
    <footer className="border-t border-black/5 bg-paper pt-16 pb-8">
      <div className="max-w-7xl mx-auto px-6 flex flex-col items-center text-center">
        <div className="mb-4 text-ink font-semibold">
          ForeverAutonomous
        </div>
        <p className="text-steel text-sm max-w-md mb-3">
          13 autonomous agents. Zero human intervention required.
          Open source under AGPL-3.0.
        </p>

        <a
          href="https://github.com/ujjwalredd/Supply-Chain"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-ink font-mono text-xs hover:text-accent transition-colors mb-12"
        >
          <Github size={16} /> Star on GitHub
        </a>

        <div className="w-full h-px bg-gradient-to-r from-transparent via-black/10 to-transparent mb-8" />

        <div className="flex flex-col md:flex-row items-center justify-between w-full text-[10px] text-steel font-medium uppercase tracking-widest">
          <span>&copy; 2026 ForeverAutonomous · AGPL-3.0 · Built by Ujjwal Reddy</span>
          <div className="flex items-center gap-6 mt-4 md:mt-0">
            <a href="https://github.com/ujjwalredd/Supply-Chain" target="_blank" className="hover:text-ink transition-colors">GitHub</a>
            <a href="https://github.com/ujjwalredd/Supply-Chain/blob/main/LICENSE" target="_blank" className="hover:text-ink transition-colors">AGPL-3.0 License</a>
            <a href="https://github.com/ujjwalredd/Supply-Chain/tree/main/agents" target="_blank" className="hover:text-ink transition-colors">13 Agents</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
