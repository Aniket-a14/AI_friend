"use client"

import React, { useRef, useEffect, useState, useCallback } from "react"
import { IntroAnimation, HERO_REVEAL_MS } from "@/components/intro-animation"
import { PixelIcon } from "@/components/pixel-icon"
import { RevealText } from "@/components/reveal-text"
import { StackingAgentCards } from "@/components/stacking-agent-cards"
import { MobileNav } from "@/components/mobile-nav"
import { DevExSection } from "@/components/devex-section"

const REPO_URL = "https://github.com/Aniket-a14/AI_friend"

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

// ─── Bento card ──────────────────────────────────────────────────────────────
function BentoCard({ children, className = "", delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const { ref, inView } = useInView(0.1)
  return (
    <div
      ref={ref}
      className={`group relative rounded-2xl border border-black/[0.07] bg-white overflow-hidden transition-all duration-700 hover:border-black/[0.15] hover:bg-[#fafaf8] ${className}`}
      style={{
        opacity: inView ? 1 : 0,
        transform: inView ? "translateY(0)" : "translateY(28px)",
        transition: `opacity 0.7s ease ${delay}ms, transform 0.7s ease ${delay}ms, border-color 0.3s ease, background-color 0.3s ease`,
      }}
    >
      <div className="pointer-events-none absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500"
        style={{ background: "radial-gradient(400px circle at var(--mouse-x, 50%) var(--mouse-y, 50%), rgba(0,0,0,0.03), transparent 60%)" }}
      />
      {children}
    </div>
  )
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
  const handleIntroDone = useCallback(() => {
    setHeroReady(true)
  }, [])

  const handleMouse = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const rect = el.getBoundingClientRect()
    el.style.setProperty("--mouse-x", `${e.clientX - rect.left}px`)
    el.style.setProperty("--mouse-y", `${e.clientY - rect.top}px`)
  }

  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">

      {/* ── INTRO ANIMATION ───────────────────────────────────────────────── */}
      <IntroAnimation onDone={handleIntroDone} />

      {/* ── STICKY NAV ────────────────────────────────────────────────────── */}
      <MobileNav />

      {/* ── HERO ──────────────────────────────────────────────────────────── */}
      <section className="relative min-h-screen flex flex-col justify-end overflow-hidden">
        {/* Soft radial gradient backdrop — no stock footage standing in for a demo that doesn't exist yet */}
        <div
          className="absolute inset-0 z-0"
          style={{
            background: "radial-gradient(120% 90% at 50% 100%, #ffffff 0%, #F5F4F0 55%, #F5F4F0 100%)",
          }}
        />

        <div className="h-20 relative z-10" />

        <div className="relative z-30 flex flex-col px-6 md:px-12 pb-16 max-w-3xl">
          <h1
            className="text-6xl sm:text-7xl md:text-8xl font-light text-[#111] leading-[1.0] tracking-tight mb-10"
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
            className="text-base sm:text-lg text-black/50 max-w-xl mb-10 leading-relaxed"
            style={{
              opacity: heroReady ? 1 : 0,
              filter: heroReady ? "blur(0px)" : "blur(16px)",
              transform: heroReady ? "translateY(0px)" : "translateY(20px)",
              transition: "opacity 0.8s cubic-bezier(0.16,1,0.3,1) 120ms, filter 0.8s cubic-bezier(0.16,1,0.3,1) 120ms, transform 0.8s cubic-bezier(0.16,1,0.3,1) 120ms",
            }}
          >
            Describe them in your own words. They speak in a voice you gave
            them, remember who you are, and run entirely on your own
            hardware — no account, no cloud, no character picker.
          </p>

          <div className="flex flex-wrap gap-3">
            {["Local-first", "MIT licensed", "Your words, your friend"].map((label, i) => (
              <div
                key={label}
                style={{
                  opacity: heroReady ? 1 : 0,
                  filter: heroReady ? "blur(0px)" : "blur(16px)",
                  transform: heroReady ? "translateY(0px)" : "translateY(20px)",
                  transition: `opacity 0.8s cubic-bezier(0.16,1,0.3,1) ${220 + i * 80}ms, filter 0.8s cubic-bezier(0.16,1,0.3,1) ${220 + i * 80}ms, transform 0.8s cubic-bezier(0.16,1,0.3,1) ${220 + i * 80}ms`,
                }}
              >
                <Tag>{label}</Tag>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── HOW IT'S DIFFERENT (bento) ─────────────────────────────────────── */}
      <section id="how" className="py-32 px-6 md:px-12 lg:px-20">
        <div className="max-w-6xl mx-auto">
          <div className="mb-16">
            <PixelIcon type="platform" size={40} />
            <div className="mt-4"><Tag>WHAT MAKES IT DIFFERENT</Tag></div>
            <RevealText className="mt-5 text-4xl md:text-5xl lg:text-6xl font-light tracking-tight leading-[1.05]">
              {"A few things here aren't\nthe obvious way to build this."}
            </RevealText>
          </div>

          <div className="grid grid-cols-12 grid-rows-auto gap-3" onMouseMove={handleMouse}>
            <BentoCard className="col-span-12 p-8 min-h-[200px] flex flex-col justify-between relative overflow-hidden" delay={0}>
              <img
                src="/images/arc.png"
                alt=""
                aria-hidden="true"
                className="absolute inset-0 w-full h-full object-cover"
                style={{ objectPosition: "center 70%" }}
              />
              <div className="absolute inset-0" style={{
                maskImage: "linear-gradient(to bottom, transparent 45%, black 100%)",
                WebkitMaskImage: "linear-gradient(to bottom, transparent 45%, black 100%)",
                backdropFilter: "blur(16px)",
                WebkitBackdropFilter: "blur(16px)",
              }} />
              <div
                className="absolute inset-0"
                style={{
                  background: "linear-gradient(to bottom, transparent 35%, rgba(245,244,240,0.3) 50%, rgba(245,244,240,0.75) 65%, rgba(245,244,240,0.95) 80%, rgb(245,244,240) 100%)",
                }}
              />
              <div className="relative z-10">
                <div className="w-10 h-10 rounded-xl border border-black/10 bg-white/60 flex items-center justify-center mb-6" style={{ backdropFilter: "blur(8px)" }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M17.657 18.657A8 8 0 1 1 6.343 7.343 8 8 0 0 1 17.657 18.657z"/><path d="M13 13a2 2 0 1 1-4 0 2 2 0 0 1 4 0z"/></svg>
                </div>
                <h3 className="text-xl font-light mb-3">Describe them, don't pick them</h3>
                <p className="text-sm text-black/45 leading-relaxed max-w-sm">
                  No template picker, no slider grid. A CLI wizard compiles your
                  prose into a persona, shows you exactly what it inferred and
                  why, and lets you try a dry-run conversation before anything
                  is permanent.
                </p>
              </div>
            </BentoCard>

            <BentoCard className="col-span-12 md:col-span-4 p-8 min-h-[200px]" delay={120}>
              <div className="w-10 h-10 rounded-xl border border-black/10 flex items-center justify-center mb-5">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              </div>
              <h3 className="text-lg font-light mb-2">A boundary that's enforced, not assumed</h3>
              <p className="text-sm text-black/45 leading-relaxed">Every persona field is sorted into an immutable safety floor, fixed temperament, or user-owned adaptive traits — checked in code, not convention.</p>
            </BentoCard>

            <BentoCard className="col-span-12 md:col-span-4 p-8 min-h-[200px]" delay={160}>
              <div className="w-10 h-10 rounded-xl border border-black/10 flex items-center justify-center mb-5">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><path d="m4.93 4.93 2.12 2.12M16.95 16.95l2.12 2.12M4.93 19.07l2.12-2.12M16.95 7.05l2.12-2.12"/></svg>
              </div>
              <h3 className="text-lg font-light mb-2">Mood that changes how it generates</h3>
              <p className="text-sm text-black/45 leading-relaxed">Cortisol and dopamine aren't decorative — they modulate LLM sampling directly. Stressed narrows the temperature; rewarded widens it.</p>
            </BentoCard>

            <BentoCard className="col-span-12 md:col-span-4 p-8 min-h-[200px]" delay={200}>
              <div className="w-10 h-10 rounded-xl border border-black/10 flex items-center justify-center mb-5">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M8 10h8M8 14h5"/></svg>
              </div>
              <h3 className="text-lg font-light mb-2">Memory that's learned, not hardcoded</h3>
              <p className="text-sm text-black/45 leading-relaxed">Retrieval expands query cues through associations the agent built from its own conversations — not a generic thesaurus doing the work.</p>
            </BentoCard>
          </div>
        </div>
      </section>

      {/* ── THE MESH ──────────────────────────────────────────────────────── */}
      <section id="mesh" className="py-32 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-8 mb-16">
            <div>
              <PixelIcon type="agents" size={40} />
              <div className="mt-4"><Tag>ARCHITECTURE</Tag></div>
              <RevealText className="mt-5 text-4xl md:text-5xl font-light tracking-tight leading-[1.05]">
                {"Separate processes,\nnot function calls."}
              </RevealText>
            </div>
            <p className="text-sm text-black/45 leading-relaxed max-w-xs">
              Agents talk over NATS JetStream with typed Pydantic contracts —
              a real signal-bus mesh, all running on your machine.
            </p>
          </div>

          <StackingAgentCards />
        </div>
      </section>

      {/* ── GET STARTED (devex code panel) ──────────────────────────────────── */}
      <DevExSection />

      {/* ── BUILT ON REAL INFRASTRUCTURE ─────────────────────────────────────── */}
      <section id="tech" className="py-32 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto">
          <div className="mb-16">
            <PixelIcon type="integrations" size={40} />
            <div className="mt-4"><Tag>THE STACK</Tag></div>
            <RevealText className="mt-5 text-4xl md:text-5xl font-light tracking-tight leading-[1.05]">
              {"Ordinary infrastructure,\nall self-hosted."}
            </RevealText>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3" onMouseMove={handleMouse}>
            {[
              { name: "Ollama", role: "Local LLM inference" },
              { name: "GPT-SoVITS", role: "Voice cloning" },
              { name: "Postgres + pgvector", role: "Identity & episodic memory" },
              { name: "Neo4j", role: "Knowledge graph" },
              { name: "Qdrant", role: "Vector similarity" },
              { name: "NATS JetStream", role: "The signal bus" },
              { name: "LiveKit", role: "WebRTC voice" },
              { name: "Rust", role: "Voice & STT runtimes" },
            ].map((t, i) => (
              <BentoCard key={t.name} className="p-6 flex flex-col justify-between min-h-[120px]" delay={i * 40}>
                <span className="font-pixel text-[10px] tracking-widest text-black/30">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <h3 className="text-base font-light mb-1">{t.name}</h3>
                  <p className="text-xs text-black/40">{t.role}</p>
                </div>
              </BentoCard>
            ))}
          </div>
        </div>
      </section>

      {/* ── PRIVACY BY DESIGN ─────────────────────────────────────────────── */}
      <section id="privacy" className="py-32 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto">
          <div className="mb-16">
            <PixelIcon type="workflow" size={40} />
            <div className="mt-4"><Tag>PRIVACY</Tag></div>
            <RevealText className="mt-5 text-4xl md:text-5xl font-light tracking-tight leading-[1.05]">
              {"Local by design,\nnot by promise."}
            </RevealText>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="space-y-6">
              <p className="text-sm text-black/45 leading-relaxed">
                No account, no conversation leaves your hardware unless you
                explicitly opt into a cloud LLM fallback for weaker machines.
              </p>

              <div className="space-y-4">
                {[
                  { label: "Local by default", desc: "Ollama and self-hosted GPT-SoVITS — nothing calls out unless you turn on the cloud fallback" },
                  { label: "No telemetry", desc: "Nothing here phones home or collects conversation logs" },
                  { label: "Yours to export", desc: "Export your friend's identity and memory, wipe the machine, import it back" },
                ].map((item) => (
                  <div key={item.label} className="flex gap-4">
                    <div className="w-1 bg-black/10 rounded-full shrink-0" />
                    <div>
                      <h3 className="text-sm font-light mb-1">{item.label}</h3>
                      <p className="text-xs text-black/35">{item.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <BentoCard className="p-6" delay={0}>
              <div className="text-xs text-black/30 tracking-widest uppercase mb-4">What stays on your machine</div>
              <div className="space-y-2">
                {[
                  { store: "Postgres + pgvector", data: "identity, episodic memory" },
                  { store: "Neo4j", data: "knowledge graph" },
                  { store: "Qdrant", data: "vector similarity index" },
                  { store: ".identity_state/", data: "personality, history" },
                  { store: "personal/", data: "your authored persona — gitignored" },
                ].map((row, i) => (
                  <div
                    key={row.store}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-black/[0.02] border border-black/[0.04]"
                    style={{ animation: `fadeInUp 0.5s cubic-bezier(0.16,1,0.3,1) ${i * 80}ms both` }}
                  >
                    <span className="text-[11px] text-black/60 font-mono min-w-[150px]">{row.store}</span>
                    <span className="text-[11px] text-black/40 font-light flex-1">{row.data}</span>
                  </div>
                ))}
              </div>
              <style>{`
                @keyframes fadeInUp {
                  from { opacity: 0; transform: translateY(8px); }
                  to { opacity: 1; transform: translateY(0); }
                }
              `}</style>
            </BentoCard>
          </div>
        </div>
      </section>

      {/* ── MARQUEE ───────────────────────────────────────────────────────── */}
      <section className="py-0 border-t border-black/[0.06] overflow-hidden select-none">
        <div className="flex border-b border-black/[0.06]" style={{ animation: "marqueeLeft 28s linear infinite" }}>
          {[...Array(3)].map((_, rep) => (
            <div key={rep} className="flex shrink-0">
              {["Remembers your day", "Has its own moods", "Speaks in a voice you gave it", "Reaches out first", "Disagrees with you sometimes", "Forgets what doesn't matter"].map((cap) => (
                <div key={cap} className="flex items-center gap-6 px-10 py-5 border-r border-black/[0.06] shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-black/20 shrink-0" />
                  <span className="text-sm text-black/45 whitespace-nowrap tracking-wide">{cap}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
        <div className="flex" style={{ animation: "marqueeRight 22s linear infinite" }}>
          {[...Array(3)].map((_, rep) => (
            <div key={rep} className="flex shrink-0">
              {["Notices when you're stressed", "Recognizes what comforts you", "Never softens on purpose", "Runs on your own hardware", "Grows through real conversation", "One friend, not a roster"].map((cap) => (
                <div key={cap} className="flex items-center gap-6 px-10 py-5 border-r border-black/[0.06] shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-black/12 shrink-0" />
                  <span className="text-sm text-black/30 whitespace-nowrap tracking-wide">{cap}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ───────────────────────────────────────────────────────────── */}
      <section className="relative py-32 px-6 md:px-12 lg:px-20 border-t border-black/[0.06] overflow-hidden">
        <img
          src="/images/footer.png"
          alt=""
          aria-hidden="true"
          className="absolute bottom-0 left-0 w-full object-cover object-bottom pointer-events-none select-none"
          style={{ opacity: 0.85 }}
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            maskImage: "linear-gradient(to top, transparent 0%, black 55%)",
            WebkitMaskImage: "linear-gradient(to top, transparent 0%, black 55%)",
            backdropFilter: "blur(18px)",
            WebkitBackdropFilter: "blur(18px)",
          }}
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: "linear-gradient(to top, rgb(245,244,240) 0%, rgba(245,244,240,0.92) 18%, rgba(245,244,240,0.55) 35%, transparent 55%)",
          }}
        />
        <div className="relative z-10 max-w-2xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-light tracking-tight leading-[1.05] mb-6">
            No waitlist.<br />It's already yours to run.
          </h2>
          <p className="text-sm text-black/45 leading-relaxed mb-10">
            Free and open source, MIT licensed. Clone it, describe your
            friend, and start talking — no account required.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 items-center justify-center">
            <code className="text-xs sm:text-sm bg-white border border-black/10 rounded-xl px-5 py-3 text-black/70 font-mono">
              git clone {REPO_URL}.git
            </code>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="px-8 py-3 bg-[#111] text-white text-sm rounded-xl hover:bg-[#333] transition-colors tracking-widest font-medium whitespace-nowrap"
            >
              VIEW ON GITHUB
            </a>
          </div>
        </div>
      </section>

      {/* ── FOOTER ────────────────────────────────────────────────────────── */}
      <footer className="py-10 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
          <span className="font-pixel text-xs tracking-[0.25em] text-black/50">AI FRIEND</span>

          <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
            {[
              { label: "How it's different", href: "#how" },
              { label: "The mesh",           href: "#mesh" },
              { label: "Get started",        href: "#setup" },
              { label: "The stack",          href: "#tech" },
              { label: "Privacy",            href: "#privacy" },
            ].map(l => (
              <a key={l.label} href={l.href} className="text-xs text-black/35 hover:text-black/70 transition-colors tracking-widest">{l.label}</a>
            ))}
          </div>

          <div className="flex items-center gap-6">
            {[
              { label: "License",      href: `${REPO_URL}/blob/main/LICENSE` },
              { label: "Contributing", href: `${REPO_URL}/blob/main/CONTRIBUTING.md` },
              { label: "Docs",         href: `${REPO_URL}/blob/main/README.md` },
              { label: "GitHub",       href: REPO_URL },
            ].map(l => (
              <a key={l.label} href={l.href} target="_blank" rel="noopener noreferrer" className="text-xs text-black/25 hover:text-black/55 transition-colors tracking-widest">{l.label}</a>
            ))}
          </div>
        </div>
        <div className="max-w-6xl mx-auto mt-8 pt-6 border-t border-black/[0.04]">
          <span className="text-xs text-black/20">MIT licensed. An open-source, self-hosted project — no service operated on your behalf.</span>
        </div>
      </footer>
    </div>
  )
}
