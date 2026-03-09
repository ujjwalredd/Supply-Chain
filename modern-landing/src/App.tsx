import { Navbar } from './components/Navbar';
import { Hero } from './components/Hero';
import { DashboardPreview } from './components/DashboardPreview';
import { OpenSourceFeature } from './components/OpenSourceFeature';
import { AIFeature } from './components/AIFeature';
import { Architecture } from './components/Architecture';
import { Footer } from './components/Footer';
import { Capabilities } from './components/Capabilities';

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
        <OpenSourceFeature />
        <Architecture />
      </main>
      
      <div className="relative z-10">
        <Footer />
      </div>
    </div>
  );
}
