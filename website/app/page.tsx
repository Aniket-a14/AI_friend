"use client"

import React, { useRef, useEffect, useState, useCallback } from "react"
import Link from "next/link"
import { IntroAnimation, HERO_REVEAL_MS } from "@/components/intro-animation"
import { PixelIcon } from "@/components/pixel-icon"
import { RevealText } from "@/components/reveal-text"
import { StackingAgentCards } from "@/components/stacking-agent-cards"
import { MobileNav } from "@/components/mobile-nav"
import { DevExSection } from "@/components/devex-section"
import { SiteFooter } from "@/components/site-footer"
import { PersonaCompilerDemo } from "@/components/persona-compiler-demo"
import { CognitiveTurnFlow } from "@/components/cognitive-turn-flow"
import { EndocrineSimulator } from "@/components/endocrine-simulator"
import { VoiceShowcase } from "@/components/voice-showcase"
import { TrustAttachmentVisualizer } from "@/components/trust-attachment-visualizer"
import { MemoryActivationVisualizer } from "@/components/memory-activation-visualizer"
import { BenchmarkPreview } from "@/components/benchmark-preview"
import { SecurityComplianceGrid } from "@/components/security-compliance-grid"
import { REPO_URL } from "@/lib/site"

// ─── Intersection Observer hook ──────────────────────────────────────────────
function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null)
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setInView(true) }, { threshold })
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])
  return { ref, inView }
}

// ─── Pill tag ─────────────────────────────────────────────────────────────────
function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] tracking-widest font-sans text-black/40 bg-black/[0.04]">
      {children}
    </span>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────
export default function LandingPage() {
  const [heroReady, setHeroReady] = useState(false)
  const [videoReady, setVideoReady] = useState(false)
  const handleIntroDone = useCallback(() => {
    setHeroReady(true)
  }, [])

  useEffect(() => {
    const t = setTimeout(() => setVideoReady(true), HERO_REVEAL_MS)
    return () => clearTimeout(t)
  }, [])

  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased selection:bg-black/10">

      {/* ── INTRO ANIMATION ───────────────────────────────────────────────── */}
      <IntroAnimation onDone={handleIntroDone} />

      {/* ── STICKY NAV ────────────────────────────────────────────────────── */}
      <MobileNav />

      {/* ── HERO ──────────────────────────────────────────────────────────── */}
      <section className="relative h-screen overflow-hidden">
        {/* Video background */}
        <video
          autoPlay
          loop
          muted
          playsInline
          className="absolute inset-0 w-full h-full object-cover z-0"
          src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/agentic-hero-9yW3wnTNMfn2U6lsVhTTZSJFEvAoSj.mp4"
          style={{
            transform: videoReady ? "scale(1.05)" : "scale(0.85)",
            transition: "transform 2s cubic-bezier(0.16, 1, 0.3, 1)",
          }}
        />

        {/* Progressive blur + light gradient rising from bottom */}
        <div className="absolute inset-x-0 bottom-0 z-10 pointer-events-none" style={{ height: "65%", background: "linear-gradient(to top, #F5F4F0 0%, #F5F4F0 18%, rgba(245,244,240,0.85) 35%, rgba(245,244,240,0.5) 55%, rgba(245,244,240,0.15) 75%, transparent 100%)" }} />
        <div className="absolute inset-x-0 bottom-0 z-10 pointer-events-none" style={{ height: "20%", backdropFilter: "blur(12px)", WebkitBackdropFilter: "blur(12px)", maskImage: "linear-gradient(to top, black 0%, transparent 100%)", WebkitMaskImage: "linear-gradient(to top, black 0%, transparent 100%)" }} />
        <div className="absolute inset-x-0 bottom-0 z-10 pointer-events-none" style={{ height: "38%", backdropFilter: "blur(6px)", WebkitBackdropFilter: "blur(6px)", maskImage: "linear-gradient(to top, black 0%, transparent 100%)", WebkitMaskImage: "linear-gradient(to top, black 0%, transparent 100%)" }} />

        <div className="absolute inset-0 z-30 flex flex-col justify-end px-6 md:px-12 pt-20 pb-10 sm:pb-16 max-w-4xl">
          <h1
            className="font-light text-[#111] tracking-tight mb-4 sm:mb-6 md:mb-8"
            style={{
              fontFamily: '"IBM Plex Sans", sans-serif',
              // vmin (the SMALLER of viewport width/height) so this shrinks for a
              // narrow-tall phone (width-constrained wrapping) and a short-wide
              // landscape phone (height-constrained) alike -- width-only Tailwind
              // breakpoints can't see either case, only vh would miss the first.
              fontSize: "clamp(1.5rem, 9vmin, 6.5rem)",
              lineHeight: 1.08,
              opacity: heroReady ? 1 : 0,
              filter: heroReady ? "blur(0px)" : "blur(24px)",
              transform: heroReady ? "translateY(0px)" : "translateY(32px)",
              transition: "opacity 1s cubic-bezier(0.16,1,0.3,1) 0ms, filter 1s cubic-bezier(0.16,1,0.3,1) 0ms, transform 1s cubic-bezier(0.16,1,0.3,1) 0ms",
            }}
          >
            A friend<br />of your own<br />making, on your<br />own machine.
          </h1>

          <p
            className="text-sm sm:text-base md:text-lg text-black/50 max-w-xl mb-4 sm:mb-6 md:mb-8 leading-relaxed [@media(max-height:480px)]:line-clamp-2"
            style={{
              opacity: heroReady ? 1 : 0,
              filter: heroReady ? "blur(0px)" : "blur(16px)",
              transform: heroReady ? "translateY(0px)" : "translateY(20px)",
              transition: "opacity 0.8s cubic-bezier(0.16,1,0.3,1) 120ms, filter 0.8s cubic-bezier(0.16,1,0.3,1) 120ms, transform 0.8s cubic-bezier(0.16,1,0.3,1) 120ms",
            }}
          >
            Describe them in your own words. They remember who you are through
            ACT-R-scored recall, build trust and attachment through real appraisal
            math, and reason through a 7-stage cognitive loop before answering in a
            cloned voice you gave them — running entirely on your own hardware,
            100% local, MIT licensed.
          </p>

          <div className="flex flex-wrap items-center gap-3 mb-3 sm:mb-4 md:mb-6">
            <Link
              href="/playground"
              className="px-6 py-3 rounded-xl bg-[#111] text-white text-xs tracking-wider font-medium hover:bg-[#333] transition-all shadow-sm flex items-center gap-2"
            >
              <span>EXPLORE PLAYGROUND</span>
              <span>→</span>
            </Link>
            <Link
              href="/docs/getting-started/installation"
              className="px-6 py-3 rounded-xl bg-white border border-black/10 text-xs tracking-wider font-medium text-black/70 hover:bg-[#fafaf8] transition-all"
            >
              READ DOCS
            </Link>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="px-6 py-3 rounded-xl bg-black/[0.04] text-xs tracking-wider font-medium text-black/60 hover:bg-black/[0.08] transition-all"
            >
              GITHUB ↗
            </a>
          </div>

          {/* Hidden on very short viewports (e.g. a phone in landscape) so this
              optional row is what gets dropped, rather than the heading
              overflowing under the fixed nav to make room for it. */}
          <div className="flex flex-wrap gap-2 [@media(max-height:480px)]:hidden">
            {["100% Local-First", "MIT Licensed", "ACT-R Memory Decay", "Tonic/Phasic Endocrine", "NATS JetStream Mesh"].map((label) => (
              <Tag key={label}>{label}</Tag>
            ))}
          </div>
        </div>
      </section>

      {/* ── SECTION 1: ENDOCRINE BIOLOGY & SAMPLING SIMULATOR (LIVE & ACTIVE) ─ */}
      <section className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="max-w-2xl">
            <PixelIcon type="integrations" size={36} />
            <div className="mt-4"><Tag>NEUROCHEMICAL SIMULATION</Tag></div>
            <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-light tracking-tight leading-[1.1]">
              Mood that changes how<br />the LLM generates words.
            </h2>
            <p className="text-sm text-black/50 mt-3 leading-relaxed">
              Cortisol and Dopamine aren't decorative strings — they mathematically modulate LLM sampling temperature, top-p, and token ceilings in real time.
            </p>
          </div>

          {/* Fully visible and live interactive endocrine biology simulator */}
          <EndocrineSimulator />
        </div>
      </section>

      {/* ── SECTION 2: 7-STAGE COGNITIVE TURN ──────────────────────────────── */}
      <section className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="max-w-2xl">
            <PixelIcon type="workflow" size={36} />
            <div className="mt-4"><Tag>THE COGNITIVE ENGINE</Tag></div>
            <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-light tracking-tight leading-[1.1]">
              Sub-second reflex &<br />deliberative appraisal.
            </h2>
            <p className="text-sm text-black/50 mt-3 leading-relaxed">
              Step through how raw 16kHz audio moves through the 9-agent asynchronous NATS signal bus from speculative emotion classification to 32kHz neural voice rendering.
            </p>
          </div>

          <CognitiveTurnFlow />
        </div>
      </section>

      {/* ── SECTION 3: INTERACTIVE COMPILER STUDIO ─────────────────────────── */}
      <section className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="max-w-2xl">
            <PixelIcon type="platform" size={36} />
            <div className="mt-4 flex items-center gap-2">
              <Tag>FREEFORM PERSONA COMPILER</Tag>
            </div>
            <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-light tracking-tight leading-[1.1]">
              Describe them in prose.<br />Never pick from a preset list.
            </h2>
            <p className="text-sm text-black/50 mt-3 leading-relaxed">
              Our compiler translates natural language into a strictly enforced 3-tier constitution (Immutable Safety Core, Constitutional Temperament, Adaptive Traits) with explainable parameter mappings.
            </p>
          </div>

          <PersonaCompilerDemo />
        </div>
      </section>

      {/* ── SECTION 4: TRUST & ATTACHMENT (LIVE, NEW) ───────────────────────── */}
      <section className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="max-w-2xl">
            <PixelIcon type="agents" size={36} />
            <div className="mt-4"><Tag>MARSH TRUST + BOWLBY ATTACHMENT</Tag></div>
            <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-light tracking-tight leading-[1.1]">
              Trust that's earned,<br />not scripted.
            </h2>
            <p className="text-sm text-black/50 mt-3 leading-relaxed">
              Every appraisal updates benevolence, competence, and integrity independently, and attachment grows on a slower, frequency-gated curve than trust does.
            </p>
          </div>

          <TrustAttachmentVisualizer />
        </div>
      </section>

      {/* ── SECTION 5: MEMORY ACTIVATION & DECAY (LIVE, NEW — replaces the old ─
             fake 3D-memory-graph "coming soon" card) ────────────────────────── */}
      <section className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="max-w-2xl">
            <PixelIcon type="pricing" size={36} />
            <div className="mt-4"><Tag>ACT-R BASE-LEVEL ACTIVATION</Tag></div>
            <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-light tracking-tight leading-[1.1]">
              Memory that decays<br />like the real thing.
            </h2>
            <p className="text-sm text-black/50 mt-3 leading-relaxed">
              Recency, frequency, importance, and emotional proximity combine into a single recall score — the exact formula every retrieval path in the backend shares.
            </p>
          </div>

          <MemoryActivationVisualizer />
        </div>
      </section>

      {/* ── SECTION 6: THE MESH ARCHITECTURE ───────────────────────────────── */}
      <section id="mesh" className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-8 mb-16">
            <div>
              <PixelIcon type="agents" size={36} />
              <div className="mt-4"><Tag>HOW THE BRAIN'S AGENTS COORDINATE</Tag></div>
              <RevealText className="mt-4 text-4xl md:text-5xl font-light tracking-tight leading-[1.05]">
                {"Separate processes,\nnot function calls."}
              </RevealText>
            </div>
            <p className="text-sm text-black/45 leading-relaxed max-w-xs">
              Agents coordinate over NATS JetStream with typed Pydantic contracts — a real signal-bus mesh, all running locally.
            </p>
          </div>

          <StackingAgentCards />
        </div>
      </section>

      {/* ── SECTION 7: GET STARTED / DEVEX ─────────────────────────────────── */}
      <DevExSection />

      {/* ── SECTION 8: ACOUSTIC PROSODY & VOICE SHOWCASE (honest, secondary) ── */}
      <section className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="max-w-2xl">
            <PixelIcon type="integrations" size={36} />
            <div className="mt-4 flex items-center gap-2">
              <Tag>VOICE — A SUPPORTING MODALITY</Tag>
            </div>
            <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-light tracking-tight leading-[1.1]">
              Studio-quality 32kHz voice,<br />cloned from 8 seconds.
            </h2>
            <p className="text-sm text-black/50 mt-3 leading-relaxed">
              The Brain drives what gets said and how it's said; GPT-SoVITS renders it with dynamic pause-bias scaling and sub-millisecond barge-in (&lt;1ms).
            </p>
          </div>

          <VoiceShowcase />
        </div>
      </section>

      {/* ── SECTION 9: EMPIRICAL BENCHMARKS & HARDWARE ──────────────────────── */}
      <section className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="max-w-2xl">
            <PixelIcon type="workflow" size={36} />
            <div className="mt-4"><Tag>EMPIRICAL MEASUREMENTS</Tag></div>
            <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-light tracking-tight leading-[1.1]">
              Measured on physical hardware.<br />No ungrounded claims.
            </h2>
            <p className="text-sm text-black/50 mt-3 leading-relaxed">
              Detailed memory footprints, latency breakdowns, and peak load stress test verification.
            </p>
          </div>

          <BenchmarkPreview />
        </div>
      </section>

      {/* ── SECTION 10: DATA SOVEREIGNTY & SECURITY ────────────────────────── */}
      <section id="privacy" className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="max-w-2xl">
            <PixelIcon type="platform" size={36} />
            <div className="mt-4"><Tag>SECURITY & PRIVACY</Tag></div>
            <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-light tracking-tight leading-[1.1]">
              Local by design,<br />not by promise.
            </h2>
            <p className="text-sm text-black/50 mt-3 leading-relaxed">
              No cloud accounts, zero telemetry, and atomic 4-store disaster recovery portability.
            </p>
          </div>

          <SecurityComplianceGrid />
        </div>
      </section>

      {/* ── SECTION 11: CTA ────────────────────────────────────────────────── */}
      <section className="relative py-32 px-6 md:px-12 lg:px-20 border-t border-black/[0.06] overflow-hidden">
        <img
          src="/images/footer.png"
          alt=""
          aria-hidden="true"
          className="absolute bottom-0 left-0 w-full object-cover object-bottom pointer-events-none select-none opacity-80"
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: "linear-gradient(to top, rgb(245,244,240) 0%, rgba(245,244,240,0.92) 20%, rgba(245,244,240,0.55) 45%, transparent 65%)",
          }}
        />
        <div className="relative z-10 max-w-2xl mx-auto text-center space-y-6">
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-light tracking-tight leading-[1.05]">
            No waitlist.<br />It's already yours to run.
          </h2>
          <p className="text-sm text-black/45 leading-relaxed">
            Free and open source, MIT licensed. Clone it, describe your
            friend, and start talking — no account required.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 items-center justify-center pt-4">
            <code className="text-xs sm:text-sm bg-white border border-black/10 rounded-xl px-5 py-3 text-black/70 font-mono shadow-xs">
              curl -fsSL {REPO_URL.replace("github.com", "raw.githubusercontent.com")}/main/scripts/install.sh | bash
            </code>
            <Link
              href="/docs/getting-started/installation"
              className="px-8 py-3 bg-[#111] text-white text-xs rounded-xl hover:bg-[#333] transition-colors tracking-widest font-medium whitespace-nowrap shadow-sm"
            >
              READ INSTALL GUIDE
            </Link>
          </div>
        </div>
      </section>

      <SiteFooter />
    </div>
  )
}
