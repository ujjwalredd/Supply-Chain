import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/react";
import { Navbar } from './components/Navbar';
import { Hero } from './components/Hero';
import { DashboardPreview } from './components/DashboardPreview';
import { OpenSourceFeature } from './components/OpenSourceFeature';
import { AIFeature } from './components/AIFeature';
import { Architecture } from './components/Architecture';
import { Footer } from './components/Footer';
import { Capabilities } from './components/Capabilities';
import { GlassBox } from './components/GlassBox';
import { DesignPartner } from './components/DesignPartner';
import { CommandPalette } from './components/CommandPalette';

export default function App() {
  return (
    <div className="min-h-screen bg-paper text-ink selection:bg-accent/20 overflow-x-hidden font-sans">
      <Navbar />

      {/* Main Content Areas */}
      <main className="relative z-10 flex flex-col min-h-screen">
        <Hero />
        <DashboardPreview />
        <AIFeature />
        <Capabilities />
        <GlassBox />
        <OpenSourceFeature />
        <Architecture />
        <DesignPartner />
      </main>

      <CommandPalette />

      <div className="relative z-10">
        <Footer />
      </div>
      <Analytics />
      <SpeedInsights />
    </div>
  );
}
