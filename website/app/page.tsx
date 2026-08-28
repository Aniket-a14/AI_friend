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
import { BenchmarkPreview } from "@/components/benchmark-preview"
import { SecurityComplianceGrid } from "@/components/security-compliance-grid"
import { ComingSoonOverlay } from "@/components/coming-soon-overlay"
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

        <div className="h-20" />

        <div className="absolute inset-x-0 bottom-0 z-30 flex flex-col px-6 md:px-12 pb-16 max-w-4xl">
          <h1
            className="text-6xl sm:text-7xl md:text-8xl font-light text-[#111] leading-[1.0] tracking-tight mb-8"
            style={{
              fontFamily: '"IBM Plex Sans", sans-serif',
              opacity: heroReady ? 1 : 0,
              filter: heroReady ? "blur(0px)" : "blur(24px)",
              transform: heroReady ? "translateY(0px)" : "translateY(32px)",
              transition: "opacity 1s cubic-bezier(0.16,1,0.3,1) 0ms, filter 1s cubic-bezier(0.16,1,0.3,1) 0ms, transform 1s cubic-bezier(0.16,1,0.3,1) 0ms",
            }}
          >
            A friend<br />of your own<br />making, on your<br />own machine.
          </h1>

          <p
            className="text-base sm:text-lg text-black/50 max-w-xl mb-8 leading-relaxed"
            style={{
              opacity: heroReady ? 1 : 0,
              filter: heroReady ? "blur(0px)" : "blur(16px)",
              transform: heroReady ? "translateY(0px)" : "translateY(20px)",
              transition: "opacity 0.8s cubic-bezier(0.16,1,0.3,1) 120ms, filter 0.8s cubic-bezier(0.16,1,0.3,1) 120ms, transform 0.8s cubic-bezier(0.16,1,0.3,1) 120ms",
            }}
          >
            Describe them in your own words. They speak in a cloned voice you gave
            them, experience biological emotions that shape their speech, remember who you are, and run entirely on your own
            hardware — 100% local, MIT licensed.
          </p>

          <div className="flex flex-wrap items-center gap-3 mb-6">
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

          <div className="flex flex-wrap gap-2">
            {["100% Local-First", "MIT Licensed", "NATS JetStream Mesh", "ACT-R Memory Decay", "Tonic/Phasic Endocrine"].map((label) => (
              <Tag key={label}>{label}</Tag>
            ))}
          </div>
        </div>
      </section>

      {/* ── SECTION 1: INTERACTIVE COMPILER STUDIO (GLOSSY BLUR OVERLAY) ─────── */}
      <section className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="max-w-2xl">
            <PixelIcon type="platform" size={36} />
            <div className="mt-4 flex items-center gap-2">
              <Tag>FREEFORM PERSONA COMPILER</Tag>
              <span className="font-mono text-[9px] uppercase tracking-widest px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300 font-semibold">
                COMING SOON
              </span>
            </div>
            <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-light tracking-tight leading-[1.1]">
              Describe them in prose.<br />Never pick from a preset list.
            </h2>
            <p className="text-sm text-black/50 mt-3 leading-relaxed">
              Our compiler translates natural language into a strictly enforced 3-tier constitution (Immutable Safety Core, Constitutional Temperament, Adaptive Traits) with explainable parameter mappings.
            </p>
          </div>

          <ComingSoonOverlay
            title="COMING SOON"
            description="In-browser interactive persona compiler and live dry-run tester is in active development for Phase 8. Full UI preview visible below."
            eta="Roadmap v7.1"
            blurAmount="md"
          >
            <PersonaCompilerDemo />
          </ComingSoonOverlay>
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

      {/* ── SECTION 3: ENDOCRINE BIOLOGY & SAMPLING SIMULATOR (LIVE & ACTIVE) ─ */}
      <section className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="max-w-2xl">
            <PixelIcon type="integrations" size={36} />
            <div className="mt-4"><Tag>NEUROBIOLOGICAL SIMULATION</Tag></div>
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

      {/* ── SECTION 4: ACOUSTIC PROSODY & VOICE SHOWCASE (GLOSSY BLUR OVERLAY) ── */}
      <section className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="max-w-2xl">
            <PixelIcon type="agents" size={36} />
            <div className="mt-4 flex items-center gap-2">
              <Tag>PHYSICAL ACOUSTIC RENDERING</Tag>
              <span className="font-mono text-[9px] uppercase tracking-widest px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300 font-semibold">
                COMING SOON
              </span>
            </div>
            <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-light tracking-tight leading-[1.1]">
              Studio-quality 32kHz voice,<br />cloned from 8 seconds.
            </h2>
            <p className="text-sm text-black/50 mt-3 leading-relaxed">
              Physical neural voice synthesis powered by GPT-SoVITS with dynamic pause bias scaling and instant 150ms barge-in interruption.
            </p>
          </div>

          <ComingSoonOverlay
            title="COMING SOON"
            description="In-browser 32kHz neural voice audio player and emotional prosody testing lab is in active development. Player layout preview visible below."
            eta="Roadmap v7.1"
            blurAmount="md"
          >
            <VoiceShowcase />
          </ComingSoonOverlay>
        </div>
      </section>

      {/* ── SECTION 5: THE MESH ARCHITECTURE ───────────────────────────────── */}
      <section id="mesh" className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-8 mb-16">
            <div>
              <PixelIcon type="agents" size={36} />
              <div className="mt-4"><Tag>THE 9-AGENT MESH</Tag></div>
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

      {/* ── SECTION 6: GET STARTED / DEVEX ─────────────────────────────────── */}
      <DevExSection />

      {/* ── SECTION 7: UPCOMING ROADMAP CAPABILITIES (GLOSSY BLUR OVERLAY) ─── */}
      <section className="py-24 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto space-y-8">
          <div className="max-w-2xl">
            <PixelIcon type="platform" size={36} />
            <div className="mt-4"><Tag>ROADMAP PREVIEW</Tag></div>
            <h2 className="mt-4 text-3xl sm:text-4xl md:text-5xl font-light tracking-tight leading-[1.1]">
              Upcoming capabilities &<br />next-generation tooling.
            </h2>
            <p className="text-sm text-black/50 mt-3 leading-relaxed">
              Features currently in active development for upcoming releases.
            </p>
          </div>

          <ComingSoonOverlay
            title="COMING SOON — ROADMAP v7.1+"
            description="WebGPU in-browser inference, 1-click cloud Colab runners, and 3D Neo4j memory graph visualizers are scheduled for the next major release."
            eta="Roadmap Target"
            blurAmount="md"
          >
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="p-6 bg-white rounded-2xl border border-black/[0.08] space-y-3">
                <span className="font-mono text-[10px] uppercase text-black/40">Browser Native</span>
                <h3 className="text-lg font-light text-[#111]">WebGPU In-Browser Voice</h3>
                <p className="text-xs text-black/50 leading-relaxed">Execute quantized 1B LLM models and ONNX voice synthesis directly in the browser via WebAssembly.</p>
                <div className="pt-2 font-mono text-[11px] text-black/40">~1.8GB Unified VRAM</div>
              </div>

              <div className="p-6 bg-white rounded-2xl border border-black/[0.08] space-y-3">
                <span className="font-mono text-[10px] uppercase text-black/40">Cloud Training</span>
                <h3 className="text-lg font-light text-[#111]">1-Click Colab Runners</h3>
                <p className="text-xs text-black/50 leading-relaxed">Offload 32kHz voice fine-tuning and benchmark sweeps to free cloud T4 GPUs with SSH tunneling.</p>
                <div className="pt-2 font-mono text-[11px] text-black/40">Zero Local Heat</div>
              </div>

              <div className="p-6 bg-white rounded-2xl border border-black/[0.08] space-y-3">
                <span className="font-mono text-[10px] uppercase text-black/40">Cognitive Visualizer</span>
                <h3 className="text-lg font-light text-[#111]">3D Memory Graph Studio</h3>
                <p className="text-xs text-black/50 leading-relaxed">Inspect spreading activation in the learned mental lexicon across Neo4j entity graphs in WebGL.</p>
                <div className="pt-2 font-mono text-[11px] text-black/40">ACT-R Decay Physics</div>
              </div>
            </div>
          </ComingSoonOverlay>
        </div>
      </section>

      {/* ── SECTION 8: EMPIRICAL BENCHMARKS & HARDWARE ──────────────────────── */}
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

      {/* ── SECTION 9: DATA SOVEREIGNTY & SECURITY ─────────────────────────── */}
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

      {/* ── SECTION 10: CTA ────────────────────────────────────────────────── */}
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
              git clone {REPO_URL}.git
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
