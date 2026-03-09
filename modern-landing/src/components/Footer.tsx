import { Activity, Github } from 'lucide-react';

export function Footer() {
  return (
    <footer className="border-t border-black/5 bg-paper pt-16 pb-8">
      <div className="max-w-7xl mx-auto px-6 flex flex-col items-center text-center">
        <div className="flex items-center gap-2 mb-6 text-ink font-semibold">
          <Activity className="text-accent" size={20} />
          Adopt AI
        </div>
        <p className="text-steel text-sm max-w-md mb-8">
          The supply chain operating system designed to collapse the gap between signal and execution. 
          Built with an ultra-premium architecture.
        </p>

        {/* Added GitHub link directly to the footer center */}
        <a 
          href="https://github.com/ujjwalredd/Supply-Chain" 
          target="_blank" 
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-ink font-mono text-xs hover:text-accent transition-colors mb-12"
        >
          <Github size={16} /> star on github 
        </a>
        
        <div className="w-full h-px bg-gradient-to-r from-transparent via-black/10 to-transparent mb-8" />
        
        <div className="flex flex-col md:flex-row items-center justify-between w-full text-[10px] text-steel font-medium uppercase tracking-widest">
          <span>&copy; 2026 Adopt AI Operating System v4.0. Designed by Ujjwal Reddy.</span>
          <div className="flex items-center gap-6 mt-4 md:mt-0">
            <a href="https://github.com/ujjwalredd/Supply-Chain" target="_blank" className="hover:text-ink transition-colors">Documentation</a>
            <a href="https://github.com/ujjwalredd/Supply-Chain" target="_blank" className="hover:text-ink transition-colors">Architecture Source</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
