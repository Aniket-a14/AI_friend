"use client"

import React from "react"
import Link from "next/link"
import { MobileNav } from "@/components/mobile-nav"
import { SiteFooter } from "@/components/site-footer"

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
            The Science of Synthetic Companionship
          </h1>
          <p className="text-base text-black/50 leading-relaxed max-w-2xl">
            A deep-dive into the cognitive architectures, neurobiological simulation equations, and memory decay formulas underlying AI Friend.
          </p>
        </div>

        {/* Paper 1: ACT-R Power-Law Memory Decay */}
        <section className="bg-white rounded-2xl border border-black/[0.08] p-6 md:p-8 space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-black/[0.06] pb-3">
            <span className="font-mono text-[10px] uppercase tracking-wider text-black/40">Memory Dynamics</span>
            <span className="text-xs text-black/40 font-mono">John R. Anderson et al.</span>
          </div>
          <h2 className="text-2xl font-light text-[#111]">ACT-R Power-Law Memory Retention</h2>
          <p className="text-sm text-black/60 leading-relaxed">
            Human memory retention does not decay linearly, nor does it remain indefinitely static. In AI Friend, base-level activation A_i of each episodic memory is computed continuously according to the power-law of forgetting:
          </p>

          <div className="bg-[#fafaf8] p-4 rounded-xl border border-black/[0.06] font-mono text-xs text-black/80 my-4 overflow-x-auto text-center">
            A_i = ln( Σ (t - t_k)^(-d) ) + Σ W_j · S_ji
          </div>

          <p className="text-xs text-black/55 leading-relaxed">
            Where (t - t_k) represents the time elapsed since the k-th recollection, d ≈ 0.5 is the decay exponent, and S_ji represents associative cues extracted through the <strong>Learned Mental Lexicon</strong>. Memories that drop below an activation threshold move to a cold tier rather than being permanently deleted.
          </p>
        </section>

        {/* Paper 2: Russell's PAD Circumplex Model of Affect */}
        <section className="bg-white rounded-2xl border border-black/[0.08] p-6 md:p-8 space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-black/[0.06] pb-3">
            <span className="font-mono text-[10px] uppercase tracking-wider text-black/40">Emotional Biology</span>
            <span className="text-xs text-black/40 font-mono">James A. Russell (1980)</span>
          </div>
          <h2 className="text-2xl font-light text-[#111]">3D Pleasure-Arousal-Dominance (PAD) Space</h2>
          <p className="text-sm text-black/60 leading-relaxed">
            Instead of coarse categorical emotion labels, AI Friend maps affect as a continuous point in a 3-dimensional Cartesian vector space:
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 my-3">
            <div className="p-3.5 bg-[#fafaf8] rounded-xl border border-black/[0.05]">
              <span className="text-xs font-semibold text-black/80 block">Pleasure (Valence)</span>
              <span className="text-[11px] text-black/45 mt-1 block">Measures hedonic tone: positive (joy, comfort) vs negative (grief, annoyance).</span>
            </div>
            <div className="p-3.5 bg-[#fafaf8] rounded-xl border border-black/[0.05]">
              <span className="text-xs font-semibold text-black/80 block">Arousal (Energy)</span>
              <span className="text-[11px] text-black/45 mt-1 block">Measures physiological activation: calm/lethargic vs alert/excited.</span>
            </div>
            <div className="p-3.5 bg-[#fafaf8] rounded-xl border border-black/[0.05]">
              <span className="text-xs font-semibold text-black/80 block">Dominance (Control)</span>
              <span className="text-[11px] text-black/45 mt-1 block">Measures perceived agency: submissive/overwhelmed vs in-control/assertive.</span>
            </div>
          </div>
        </section>

        {/* Paper 3: Neurochemical Modulation & Anti-Sycophancy */}
        <section className="bg-white rounded-2xl border border-black/[0.08] p-6 md:p-8 space-y-4 shadow-sm">
          <div className="flex items-center justify-between border-b border-black/[0.06] pb-3">
            <span className="font-mono text-[10px] uppercase tracking-wider text-black/40">Cognitive Scaffolding</span>
            <span className="text-xs text-black/40 font-mono">Anti-Sycophancy Architecture</span>
          </div>
          <h2 className="text-2xl font-light text-[#111]">Tonic/Phasic Endocrine Sampling & Disagreement</h2>
          <p className="text-sm text-black/60 leading-relaxed">
            Most LLM assistants are trained to maximize user flattery, creating an uncanny, artificial dynamic. AI Friend pairs an endocrine simulation (independent Cortisol and Dopamine bursts) with an explicit <strong>Anti-Sycophancy Scaffolding</strong> in the deliberation engine.
          </p>
          <div className="bg-[#fafaf8] p-4 rounded-xl border border-black/[0.06] text-xs text-black/60 space-y-2">
            <p><strong>1. Phasic Burst Dynamics:</strong> Phasic(t) = Phasic₀ · e^(-λt), where λ = ln(2) / t_half (600s for stress, 90s for reward).</p>
            <p><strong>2. Sampling Parameter Modulation:</strong> Temperature = f(Cortisol), Top-P = g(Dopamine), Max Tokens = h(Fatigue).</p>
            <p><strong>3. Preserved Disagreement:</strong> Deliberation behavior trees assign positive utility to pushing back against fallacies rather than nodding along.</p>
          </div>
        </section>

        {/* CTA */}
        <div className="pt-6 border-t border-black/[0.06] flex items-center justify-between">
          <span className="text-xs text-black/40">Read the complete technical implementation details in the docs.</span>
          <Link href="/docs/concepts/endocrine-affect-system" className="text-xs font-medium text-black underline underline-offset-4">
            Endocrine Documentation →
          </Link>
        </div>
      </main>

      <SiteFooter />
    </div>
  )
}
