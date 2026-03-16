import { Github, Mail, Linkedin } from 'lucide-react';

const STATS = [
  { label: 'Agents running 24/7', value: '13' },
  { label: 'Automated tests',     value: '203' },
  { label: 'Model ROC-AUC',       value: '0.86+' },
  { label: 'Early warning lead',  value: '4.2h' },
];

export function Footer() {
  return (
    <footer className="border-t border-black/5 bg-paper pt-16 pb-8">
      <div className="max-w-7xl mx-auto px-6">

        {/* Stats strip */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 pb-10 border-b border-black/5 mb-10">
          {STATS.map(s => (
            <div key={s.label} className="flex flex-col gap-0.5">
              <span className="text-2xl font-bold text-ink tracking-tight">{s.value}</span>
              <span className="text-[10px] font-mono text-steel uppercase tracking-widest">{s.label}</span>
            </div>
          ))}
        </div>

        {/* Main footer row */}
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
          <div>
            <div className="font-semibold text-ink mb-1">ForeverAutonomous</div>
            <p className="text-steel text-sm max-w-sm font-light leading-relaxed">
              Open-source autonomous supply chain OS. 13 AI agents, self-healing pipelines, zero human intervention.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <a
              href="https://github.com/ujjwalredd/Supply-Chain"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 border border-black/10 text-ink px-4 py-2 rounded-lg hover:bg-subtle hover:border-black/15 transition-colors font-medium text-xs"
            >
              <Github size={14} /> GitHub
            </a>
            <a
              href="https://www.linkedin.com/in/ujjwalreddyks/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 border border-black/10 text-ink px-4 py-2 rounded-lg hover:bg-subtle hover:border-black/15 transition-colors font-medium text-xs"
            >
              <Linkedin size={14} /> LinkedIn
            </a>
            <a
              href="mailto:ujjwalreddyks@gmail.com"
              className="flex items-center gap-2 border border-black/10 text-ink px-4 py-2 rounded-lg hover:bg-subtle hover:border-black/15 transition-colors font-medium text-xs"
            >
              <Mail size={14} /> Email
            </a>
          </div>
        </div>

        <div className="w-full h-px bg-gradient-to-r from-transparent via-black/10 to-transparent mt-10 mb-6" />

        <div className="flex flex-col md:flex-row items-center justify-between text-[10px] text-steel font-medium uppercase tracking-widest gap-3">
          <span>&copy; 2026 ForeverAutonomous · AGPL-3.0 · Built by Ujjwal Reddy</span>
          <div className="flex items-center gap-6">
            <a href="https://github.com/ujjwalredd/Supply-Chain" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors">GitHub</a>
            <a href="https://github.com/ujjwalredd/Supply-Chain/blob/main/LICENSE" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors">AGPL-3.0</a>
            <a href="https://github.com/ujjwalredd/Supply-Chain/tree/main/agents" target="_blank" rel="noopener noreferrer" className="hover:text-ink transition-colors">13 Agents</a>
            <a href="#design-partner" className="hover:text-ink transition-colors">Design Partner</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
