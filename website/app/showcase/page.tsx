"use client"

import React, { useState } from "react"
import { MobileNav } from "@/components/mobile-nav"
import { SiteFooter } from "@/components/site-footer"
import { PERSONA_PRESETS, COMPANION_RECIPES } from "@/lib/showcase-data"
import { ComingSoonOverlay } from "@/components/coming-soon-overlay"

export default function ShowcasePage() {
  const [selectedPresetId, setSelectedPresetId] = useState<string>(PERSONA_PRESETS[0].id)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const activePreset = PERSONA_PRESETS.find((p) => p.id === selectedPresetId) || PERSONA_PRESETS[0]

  const handleCopyPreset = (preset: typeof PERSONA_PRESETS[0]) => {
    navigator.clipboard.writeText(preset.proseDescription)
    setCopiedId(preset.id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />

      <main className="max-w-6xl mx-auto px-6 md:px-12 pt-36 pb-24 space-y-16">
        {/* Header */}
        <div className="max-w-3xl">
          <div className="mb-3 inline-flex items-center gap-2 font-mono text-xs text-black/40">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Companion Relationship Archetypes & Architecture
          </div>
          <h1 className="text-4xl sm:text-5xl font-light tracking-tight text-[#111] mb-4" style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}>
            Friendship Dynamics & Companion Showcase
          </h1>
          <p className="text-base text-black/50 leading-relaxed">
            AI Friend is an authentic, lifelong companion — not a robotic voice assistant or sycophantic chatbot. Explore how real relationship friction, biological mood drift, and episodic memory create a genuine friend of your own making.
          </p>
        </div>

        {/* Section 1: Curated Companion Relationship Dynamics */}
        <section className="space-y-8">
          <div className="border-b border-black/[0.08] pb-4 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-black/40">Real Companion Dynamics</span>
              <h2 className="text-2xl font-light text-[#111] mt-1">Curated Relationship Presets</h2>
              <p className="text-xs text-black/50 mt-1">
                Select a companion archetype to inspect their authentic friction behavior, biological temperament, and cloned voice profile.
              </p>
            </div>

            {/* Quick Archetype Switcher */}
            <div className="flex flex-wrap gap-1.5">
              {PERSONA_PRESETS.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelectedPresetId(p.id)}
                  className={`px-3 py-1.5 rounded-xl text-xs transition-all ${
                    selectedPresetId === p.id
                      ? "bg-[#111] text-white shadow-xs font-medium"
                      : "bg-white text-black/60 border border-black/[0.06] hover:bg-black/[0.04]"
                  }`}
                >
                  {p.name} · {p.relationshipRole.split(" ")[1]}
                </button>
              ))}
            </div>
          </div>

          {/* Active Companion Feature Showcase Card */}
          <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm space-y-8">
            <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 border-b border-black/[0.06] pb-6">
              <div>
                <div className="inline-flex items-center gap-2 mb-2">
                  <span className="font-mono text-[10px] uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">
                    {activePreset.relationshipDynamics.attachmentStyle} Bond
                  </span>
                  <span className="text-xs text-black/40 font-mono">
                    Trust Depth: {activePreset.relationshipDynamics.trustDepth}
                  </span>
                </div>
                <h3 className="text-3xl font-light text-[#111]">{activePreset.name}</h3>
                <p className="text-sm font-medium text-black/60 mt-0.5">{activePreset.relationshipRole}</p>
                <p className="text-xs text-black/50 italic mt-2">"{activePreset.tagline}"</p>
              </div>

              <div className="flex items-center gap-2 self-start md:self-auto">
                <button
                  onClick={() => handleCopyPreset(activePreset)}
                  className="px-4 py-2 rounded-xl bg-[#111] text-white text-xs font-medium hover:bg-[#333] transition-colors flex items-center gap-1.5 shadow-2xs"
                >
                  <span>{copiedId === activePreset.id ? "✓ Copied!" : "Copy Onboarding Prose"}</span>
                </button>
              </div>
            </div>

            {/* Prose description */}
            <div className="bg-[#fafaf8] p-4 md:p-5 rounded-xl border border-black/[0.05]">
              <span className="font-mono text-[10px] uppercase tracking-wider text-black/35 block mb-1.5">Authored Character Biography</span>
              <p className="text-xs sm:text-sm text-black/75 leading-relaxed font-sans">
                {activePreset.proseDescription}
              </p>
            </div>

            {/* Relationship Dynamics Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-xl border border-black/[0.06] bg-[#fafaf8] space-y-1.5">
                <span className="font-mono text-[10px] uppercase tracking-wider text-rose-700/80 block">Authentic Friction</span>
                <p className="text-xs text-black/65 leading-relaxed">{activePreset.relationshipDynamics.frictionStyle}</p>
              </div>

              <div className="p-4 rounded-xl border border-black/[0.06] bg-[#fafaf8] space-y-1.5">
                <span className="font-mono text-[10px] uppercase tracking-wider text-blue-700/80 block">Proactive Presence</span>
                <p className="text-xs text-black/65 leading-relaxed">{activePreset.relationshipDynamics.proactiveOutreach}</p>
              </div>

              <div className="p-4 rounded-xl border border-black/[0.06] bg-[#fafaf8] space-y-1.5">
                <span className="font-mono text-[10px] uppercase tracking-wider text-amber-700/80 block">Voice Cadence & Prosody</span>
                <p className="text-xs text-black/65 leading-relaxed">{activePreset.voiceProfile.cadence} · {activePreset.voiceProfile.description}</p>
              </div>
            </div>

            {/* Live Dialogue Exchange demonstrating Authentic Friction */}
            <div className="rounded-xl border border-black/[0.07] bg-white p-5 space-y-3">
              <span className="font-mono text-[10px] uppercase tracking-widest text-black/40 block border-b border-black/[0.06] pb-2">
                Simulated Conversation: Preserved Emotional Friction
              </span>

              <div className="bg-black/[0.03] p-3.5 rounded-lg text-xs text-black/80 max-w-[85%] border border-black/[0.04]">
                <span className="font-mono text-[10px] text-black/40 block mb-1 uppercase">You</span>
                "{activePreset.sampleDialogue.user}"
              </div>

              <div className="bg-[#fafaf8] p-4 rounded-lg text-xs text-black/90 max-w-[85%] ml-auto border border-black/[0.08] shadow-2xs">
                <span className="font-mono text-[10px] text-emerald-700/80 block mb-1 uppercase font-semibold">
                  {activePreset.name} (Friend)
                </span>
                "{activePreset.sampleDialogue.friendResponse}"
                <div className="mt-3 pt-2 border-t border-black/[0.06] flex flex-wrap justify-between items-center text-[10px] font-mono text-black/45">
                  <span>{activePreset.sampleDialogue.internalAffect}</span>
                  <span className="text-emerald-700 font-medium">{activePreset.sampleDialogue.frictionNote}</span>
                </div>
              </div>
            </div>

            {/* Memory Lexicon Seeds */}
            <div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-black/35 block mb-2">Learned Lexicon Anchors</span>
              <div className="flex flex-wrap gap-1.5">
                {activePreset.memoryLexiconSeeds.map((seed) => (
                  <span key={seed} className="px-2.5 py-1 rounded-md bg-black/[0.04] text-[11px] font-mono text-black/70">
                    #{seed}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* Section 2: Companion Architecture Recipes */}
        <section className="space-y-6">
          <div className="border-b border-black/[0.08] pb-4">
            <span className="text-[10px] font-mono uppercase tracking-widest text-black/40">Architecture & Mechanics</span>
            <h2 className="text-2xl font-light text-[#111] mt-1">Companion Creation & Seeding Guides</h2>
            <p className="text-xs text-black/50 mt-1">
              How the 4 cognitive layers combine to turn an LLM into an embodied personal friend.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {COMPANION_RECIPES.map((recipe) => (
              <div key={recipe.id} className="bg-white rounded-2xl border border-black/[0.08] p-6 flex flex-col justify-between shadow-xs space-y-4">
                <div className="space-y-3">
                  <span className="font-mono text-[9px] uppercase tracking-widest px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-800 border border-blue-200">
                    {recipe.category}
                  </span>
                  <h3 className="text-lg font-light text-[#111]">{recipe.title}</h3>
                  <p className="text-xs text-black/60 leading-relaxed">{recipe.description}</p>

                  <ul className="space-y-1.5 list-disc pl-4 text-xs text-black/65 leading-relaxed pt-2">
                    {recipe.implementationDetails.map((detail, idx) => (
                      <li key={idx}>{detail}</li>
                    ))}
                  </ul>

                  {/* Code snippet preview */}
                  <div className="bg-[#fafaf8] p-3 rounded-xl border border-black/[0.06] font-mono text-[11px] text-black/80 overflow-x-auto">
                    <pre className="text-black/70 leading-snug">{recipe.codeSnippet}</pre>
                  </div>
                </div>

                <div className="pt-3 border-t border-black/[0.05] text-[10px] font-mono text-black/40">
                  Target files: {recipe.targetFiles.join(", ")}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Section 3: Community Persona Registry (Coming Soon Overlay) */}
        <section className="space-y-6">
          <div className="border-b border-black/[0.08] pb-4 flex items-center justify-between">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-black/40">Community Hub</span>
              <h2 className="text-2xl font-light text-[#111] mt-1">Community Persona Registry</h2>
              <p className="text-xs text-black/50 mt-1">
                Browse and share community-authored personality constitutions and acoustic presets.
              </p>
            </div>
            <span className="font-mono text-[9px] uppercase tracking-widest px-2.5 py-1 rounded-full bg-amber-100 text-amber-900 border border-amber-300 font-semibold">
              COMING SOON
            </span>
          </div>

          <ComingSoonOverlay
            title="COMING SOON"
            description="The public persona sharing registry and 1-click import system is launching alongside the community hub."
            eta="Roadmap v7.2"
            blurAmount="md"
          >
            <div className="rounded-2xl border border-black/[0.08] bg-white p-8 grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-5 bg-[#fafaf8] rounded-xl border border-black/[0.05] space-y-2">
                <span className="text-xs font-semibold text-black/80">Public Archetype Gallery</span>
                <p className="text-xs text-black/55 leading-relaxed">Search through thousands of open-source personality seeds rated by community members.</p>
              </div>
              <div className="p-5 bg-[#fafaf8] rounded-xl border border-black/[0.05] space-y-2">
                <span className="text-xs font-semibold text-black/80">1-Click Local Import</span>
                <p className="text-xs text-black/55 leading-relaxed">Import any community persona into your local database using a single shareable URL.</p>
              </div>
            </div>
          </ComingSoonOverlay>
        </section>
      </main>

      <SiteFooter />
    </div>
  )
}
