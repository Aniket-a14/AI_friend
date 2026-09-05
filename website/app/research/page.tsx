"use client"

import React from "react"
import Link from "next/link"
import { MobileNav } from "@/components/mobile-nav"
import { SiteFooter } from "@/components/site-footer"
import { RESEARCH_CITATIONS, PILLAR_LABELS, PILLAR_ORDER, type ResearchPillar } from "@/lib/research-citations"

function CitationList({ pillar }: { pillar: ResearchPillar }) {
  const citations = RESEARCH_CITATIONS.filter((c) => c.pillar === pillar)
  return (
    <div className="space-y-3">
      {citations.map((c) => (
        <a
          key={c.id}
          href={c.link}
          target="_blank"
          rel="noopener noreferrer"
          className="block p-3.5 bg-[#fafaf8] rounded-xl border border-black/[0.05] hover:border-black/15 transition-colors group"
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <span className="text-xs font-semibold text-black/80">{c.authors} ({c.year})</span>
              <p className="text-xs text-black/70 mt-0.5">{c.title}</p>
              <span className="text-[11px] text-black/40 italic">{c.venue}</span>
            </div>
            <span className="text-[10px] text-black/30 group-hover:text-black/60 whitespace-nowrap mt-0.5">↗</span>
          </div>
          <p className="text-[11px] text-black/50 mt-2 leading-relaxed border-t border-black/[0.05] pt-2">{c.relevance}</p>
        </a>
      ))}
    </div>
  )
}

function PillarSection({
  pillar,
  eyebrow,
  title,
  intro,
  children,
}: {
  pillar: ResearchPillar
  eyebrow: string
  title: string
  intro: string
  children?: React.ReactNode
}) {
  return (
    <section className="bg-white rounded-2xl border border-black/[0.08] p-6 md:p-8 space-y-5 shadow-sm">
      <div className="border-b border-black/[0.06] pb-3">
        <span className="font-mono text-[10px] uppercase tracking-wider text-black/40">{eyebrow}</span>
        <h2 className="text-2xl font-light text-[#111] mt-1">{title}</h2>
      </div>
      <p className="text-sm text-black/60 leading-relaxed">{intro}</p>
      {children}
      <div className="pt-2">
        <span className="text-[10px] font-mono uppercase tracking-widest text-black/35 block mb-3">
          {PILLAR_LABELS[pillar]} — Citations
        </span>
        <CitationList pillar={pillar} />
      </div>
    </section>
  )
}

export default function ResearchPage() {
  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />

      <main className="max-w-4xl mx-auto px-6 md:px-12 pt-36 pb-24 space-y-16">
        {/* Header */}
        <div>
          <div className="mb-3 inline-flex items-center gap-2 font-mono text-xs text-black/40">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan-500" />
            Cognitive Science & Academic Foundations
          </div>
          <h1 className="text-4xl sm:text-5xl font-light tracking-tight text-[#111] mb-4" style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}>
            The research behind the Brain.
          </h1>
          <p className="text-base text-black/50 leading-relaxed max-w-2xl">
            The cognitive architecture, affect dynamics, and memory retrieval this system implements are
            structurally inspired by a specific, citable body of work in cognitive science, affective
            computing, and information retrieval. Voice and vision draw on a shorter, more supporting
            literature further down this page.
          </p>
        </div>

        {/* Methodology callout */}
        <div className="bg-black/[0.03] border border-black/[0.08] rounded-2xl p-6 space-y-2">
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/40">Methodology</span>
          <p className="text-sm text-black/65 leading-relaxed">
            These are mechanisms this architecture draws structural inspiration from — not benchmarks it claims
            to beat. Citing HippoRAG doesn't mean this system outperforms HippoRAG's own reported numbers, and
            citing Anderson's ACT-R doesn't mean this reimplements ACT-R in full. This project's own measured
            numbers live at <Link href="/benchmarks" className="underline">/benchmarks</Link>, independently
            captured against this codebase and labeled with their provenance — not derived from, or compared
            against, any paper below. Every link on this page was checked to actually resolve to the paper it
            claims to be before publishing.
          </p>
        </div>

        {/* Pillar B: Affective Computing & Appraisal */}
        <PillarSection
          pillar="affective-computing"
          eyebrow="Pillar B — Emotional Biology"
          title="Affective Computing & Appraisal"
          intro="Instead of coarse categorical emotion labels or a stateless prompt prefix, this system represents affect as a continuous point in a 3-dimensional Pleasure-Arousal-Dominance space, updated each turn by an appraisal step, and layers a tonic + phasic endocrine simulation on top that actually changes LLM sampling parameters."
        >
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 my-3">
            <div className="p-3.5 bg-[#fafaf8] rounded-xl border border-black/[0.05]">
              <span className="text-xs font-semibold text-black/80 block">Pleasure (Valence)</span>
              <span className="text-[11px] text-black/45 mt-1 block">Hedonic tone: positive (joy, comfort) vs. negative (grief, annoyance).</span>
            </div>
            <div className="p-3.5 bg-[#fafaf8] rounded-xl border border-black/[0.05]">
              <span className="text-xs font-semibold text-black/80 block">Arousal (Energy)</span>
              <span className="text-[11px] text-black/45 mt-1 block">Physiological activation: calm/lethargic vs. alert/excited.</span>
            </div>
            <div className="p-3.5 bg-[#fafaf8] rounded-xl border border-black/[0.05]">
              <span className="text-xs font-semibold text-black/80 block">Dominance (Control)</span>
              <span className="text-[11px] text-black/45 mt-1 block">Perceived agency: submissive/overwhelmed vs. in-control/assertive.</span>
            </div>
          </div>

          <div className="bg-[#fafaf8] p-4 rounded-xl border border-black/[0.06] text-xs text-black/60 space-y-2">
            <p><strong>1. Phasic burst decay:</strong> phasic(t) = peak · e^(−λt), where λ = ln(2) / half-life. Cortisol's half-life is 4500s and dopamine's is 90s — deliberately asymmetric, because a fright should linger far longer than a reward's glow.</p>
            <p><strong>2. Tonic + phasic split:</strong> the tonic terms are pure functions of current valence/arousal and so are perfectly anti-correlated by construction; only the phasic channels let the agent be stressed and rewarded at once.</p>
            <p><strong>3. Sampling modulation:</strong> cortisol narrows LLM temperature, dopamine widens top-p, fatigue shortens the token ceiling — see{" "}
              <Link href="/docs/concepts/endocrine-affect-system" className="underline">the endocrine docs</Link> for the exact formulas and the live simulator on{" "}
              <Link href="/playground" className="underline">the playground</Link>.
            </p>
          </div>
        </PillarSection>

        {/* Pillar C: ACT-R Memory & Hybrid Retrieval */}
        <PillarSection
          pillar="act-r-memory"
          eyebrow="Pillar C — Memory Dynamics"
          title="ACT-R Memory & Hybrid Vector-Graph Retrieval"
          intro="Memory retention doesn't decay linearly, nor stay indefinitely static. Recall scoring combines a single-term approximation of Anderson's ACT-R base-level activation with a Personalized-PageRank graph boost over a Neo4j semantic network and an affect-gated similarity term."
        >
          <div className="bg-[#fafaf8] p-4 rounded-xl border border-black/[0.06] font-mono text-xs text-black/80 my-4 overflow-x-auto text-center">
            A_i = ln(recall_count) − d · ln(hours_since_last + 1) + 1.5 · importance + 0.15 · (1 − dist_emo)
          </div>
          <p className="text-xs text-black/55 leading-relaxed">
            Where <code>hours_since_last</code> is time elapsed since the memory's last recollection, d ≈ 0.5
            is the decay rate, <code>importance</code> is a stored per-memory weight, and <code>dist_emo</code>
            is emotional distance between the memory's affect and the agent's current affect. Try the exact
            formula live, including massed-vs-spaced recall, on{" "}
            <Link href="/playground" className="underline">the playground</Link>.
          </p>
        </PillarSection>

        {/* Pillar A: Turn-Taking & Interaction Latency (voice-secondary) */}
        <PillarSection
          pillar="turn-taking"
          eyebrow="Pillar A — Voice, a supporting modality"
          title="Turn-Taking & Interaction Latency"
          intro="Natural human conversation runs on turn-transition gaps around 200ms. Sequential ASR → LLM → TTS pipelines routinely blow past that; the speculative pre-generation and Voice-Activity-Projection-style prediction below are the literature this project's turn-taking reflex draws from."
        />

        {/* Pillar D: Edge Middleware & Local Multi-Agent Inference */}
        <PillarSection
          pillar="edge-middleware"
          eyebrow="Pillar D — Infrastructure"
          title="Edge Middleware & Local Multi-Agent Inference"
          intro="Agents in this system are separate processes coordinated over NATS JetStream rather than function calls, with latency-critical voice and STT paths written in Rust behind a Python control plane, so it can run entirely on local hardware."
        />

        {/* Pillar E: Lifespan Development & Neuromorphic Memory */}
        <PillarSection
          pillar="lifespan-development"
          eyebrow="Pillar E — Long-Horizon Memory"
          title="Lifespan Development & Neuromorphic Memory"
          intro="A companion relationship that matters is one that deepens over a real timeline, not one that resets each session. Complementary Learning Systems theory — fast episodic memory consolidating into slower, structured long-term memory — is the direct model behind this system's sleep-cycle consolidation pass."
        />

        {/* Vendor / Industry Context */}
        <section className="bg-white rounded-2xl border border-black/[0.08] p-6 md:p-8 space-y-4 shadow-sm">
          <div className="border-b border-black/[0.06] pb-3 flex items-center justify-between flex-wrap gap-2">
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-black/40">Industry Context</span>
              <h2 className="text-2xl font-light text-[#111] mt-1">Where this sits next to commercial humanoid platforms</h2>
            </div>
            <span className="font-mono text-[9px] uppercase tracking-widest px-2.5 py-1 rounded-full bg-amber-100 text-amber-900 border border-amber-300 font-semibold whitespace-nowrap">
              Not Peer-Reviewed
            </span>
          </div>
          <p className="text-sm text-black/60 leading-relaxed">
            Humanoid platforms like Figure, Tesla Optimus, Unitree's G1, Engineered Arts' Ameca, and Kyoto's
            ERICA are named here only as industry context for the conversational-AI space this project sits
            in — their public specs and demos are vendor/lab claims, not peer-reviewed publications, and this
            project makes no benchmark comparison against them here.
          </p>
          <p className="text-xs text-black/50 leading-relaxed bg-[#fafaf8] rounded-xl border border-black/[0.06] p-3.5">
            <strong>This matters for scope, too:</strong> physical robotics body-hardware actuation is explicitly
            <strong> not implemented</strong> in this codebase — it's realized only via fail-closed external
            dispatcher stubs. This project is a cognitive/affect/memory architecture (the Brain) with a voice
            pipeline and appraisal-only vision input; it does not drive a physical robot body today.
          </p>
        </section>

        {/* CTA */}
        <div className="pt-6 border-t border-black/[0.06] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <span className="text-xs text-black/40">Read the implementation details, or see this project's own measured numbers.</span>
          <div className="flex gap-4">
            <Link href="/docs/concepts/architecture-of-mind" className="text-xs font-medium text-black underline underline-offset-4">
              Architecture of Mind →
            </Link>
            <Link href="/benchmarks" className="text-xs font-medium text-black underline underline-offset-4">
              Benchmarks →
            </Link>
          </div>
        </div>
      </main>

      <SiteFooter />
    </div>
  )
}
