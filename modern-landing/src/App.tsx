import { useEffect, useRef } from "react";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/react";
import { motion } from 'framer-motion';
import { Navbar } from './components/Navbar';
import { Hero } from './components/Hero';
import { EventTape } from './components/EventTape';
import { ImpactNumbers } from './components/ImpactNumbers';
import { DashboardPreview } from './components/DashboardPreview';
import { BeforeAfter } from './components/BeforeAfter';
import { OpenSourceFeature } from './components/OpenSourceFeature';
import { AIFeature } from './components/AIFeature';
import { AgentFlowMap } from './components/AgentFlowMap';
import { AgentHeatmap } from './components/AgentHeatmap';
import { PipelineFlow } from './components/PipelineFlow';
import { Architecture } from './components/Architecture';
import { Footer } from './components/Footer';
import { Capabilities } from './components/Capabilities';
import { GlassBox } from './components/GlassBox';
import { TrustSecurity } from './components/TrustSecurity';
import { DesignPartner } from './components/DesignPartner';
import { CommandPalette } from './components/CommandPalette';
import { CustomCursor } from './components/CustomCursor';
import { ScrollProgress } from './components/ScrollProgress';

function Divider({ number, title, subtitle }: { number: string; title: string; subtitle: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.5 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="max-w-7xl mx-auto px-6 pt-16 pb-4 flex flex-col gap-1"
    >
      <span className="text-[10px] font-mono text-steel/40 uppercase tracking-[0.2em]">{number}</span>
      <div className="flex items-baseline gap-4 flex-wrap">
        <h2 className="text-xl font-semibold text-ink tracking-tight">{title}</h2>
        <span className="text-steel text-sm font-light hidden sm:block">{subtitle}</span>
      </div>
      <div className="mt-3 h-px w-full bg-gradient-to-r from-black/6 via-black/3 to-transparent" />
    </motion.div>
  );
}

function usePageTitleScroll() {
  const sections = useRef([
    { id: 'impact',         title: 'ForeverAutonomous — 4.2h Early Warning' },
    { id: 'dashboard',      title: 'ForeverAutonomous — Control Tower' },
    { id: 'platform',       title: 'ForeverAutonomous — 13 Agents' },
    { id: 'architecture',   title: 'ForeverAutonomous — Pipeline' },
    { id: 'design-partner', title: 'ForeverAutonomous — Design Partner' },
  ]);

  useEffect(() => {
    const defaultTitle = 'ForeverAutonomous — 13 AI Agents. Zero Human Intervention.';
    const observers: IntersectionObserver[] = [];

    sections.current.forEach(({ id, title }) => {
      const el = document.getElementById(id);
      if (!el) return;
      const obs = new IntersectionObserver(
        ([e]) => { if (e.isIntersecting) document.title = title; },
        { threshold: 0.4 }
      );
      obs.observe(el);
      observers.push(obs);
    });

    const onScroll = () => { if (window.scrollY < 200) document.title = defaultTitle; };
    window.addEventListener('scroll', onScroll, { passive: true });

    return () => {
      observers.forEach(o => o.disconnect());
      window.removeEventListener('scroll', onScroll);
      document.title = defaultTitle;
    };
  }, []);
}

export default function App() {
  usePageTitleScroll();

  return (
    <div className="min-h-screen bg-paper text-ink selection:bg-accent/20 overflow-x-hidden font-sans">
      <ScrollProgress />
      <CustomCursor />
      <Navbar />

      <main>
        {/* ── ACT 1: HOOK ─────────────────────────────── */}
        <Hero />

        {/* ── LIVE EVENT TAPE — CSS-only, zero JS ─────── */}
        <EventTape />

        {/* ── BY THE NUMBERS ──────────────────────────── */}
        <div id="impact"><ImpactNumbers /></div>

        {/* ── ACT 2: THE PROBLEM ──────────────────────── */}
        <Divider
          number="01  The Problem"
          title="Supply chains break silently."
          subtitle="By the time your team sees it, the damage is done."
        />
        <div id="dashboard"><DashboardPreview /></div>

        {/* ── BEFORE / AFTER GANTT TIMELINES ──────────── */}
        <BeforeAfter />

        {/* ── ACT 3: THE SYSTEM ───────────────────────── */}
        <Divider
          number="02  The System"
          title="13 agents. One orchestrator. Zero gaps."
          subtitle="Every agent runs on its own schedule, self-heals, and escalates only when genuinely needed."
        />
        <div id="platform">
          <AIFeature />
          <AgentFlowMap />
          <AgentHeatmap />
        </div>

        {/* ── ACT 4: THE ENGINE ───────────────────────── */}
        <Divider
          number="03  The Engine"
          title="22 containers. Enterprise-grade. Fully open."
          subtitle="The same stack powering $100M+ operations towers — self-hosted, yours to own."
        />
        <Capabilities />

        {/* ── ACT 5: THE GUARDRAILS ───────────────────── */}
        <Divider
          number="04  The Guardrails"
          title="Autonomous when safe. Human when it matters."
          subtitle="Configure exactly what the system can do on its own and what it brings to you."
        />
        <GlassBox />

        {/* ── ACT 6: GOVERNANCE & SECURITY ────────────── */}
        <Divider
          number="05  Governance & Security"
          title="Data governance. AI security. Full trustworthiness."
          subtitle="Three independent layers — harden every model interaction, make every decision replayable, control exactly what data moves where."
        />
        <TrustSecurity />

        {/* ── ACT 7: THE PIPELINE ─────────────────────── */}
        <Divider
          number="06  The Pipeline"
          title="Pipeline triggered in 60 seconds. Insights live in 15 minutes."
          subtitle="Drop any file. Schema is inferred. Pipeline triggers. Agents activate."
        />
        <PipelineFlow />
        <div id="architecture"><Architecture /></div>

        {/* ── ACT 8: OPEN SOURCE ──────────────────────── */}
        <Divider
          number="07  Open Source"
          title="Every line of code is public. AGPL-3.0."
          subtitle="No black boxes. No vendor lock. Fork it, run it, build on it."
        />
        <OpenSourceFeature />

        {/* ── ACT 9: GET INVOLVED ─────────────────────── */}
        <Divider
          number="08  Get Involved"
          title="Be one of the first operators to run this."
          subtitle="Design partners get full access, direct line to the team, and shape what gets built."
        />
        <div id="design-partner"><DesignPartner /></div>
      </main>

      <CommandPalette />
      <Footer />
      <Analytics />
      <SpeedInsights />
    </div>
  );
}
