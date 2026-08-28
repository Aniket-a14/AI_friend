"use client"

import React, { useState } from "react"
import { PERSONA_PRESETS } from "@/lib/showcase-data"

export function PersonaCompilerDemo() {
  const [selectedPresetId, setSelectedPresetId] = useState(PERSONA_PRESETS[0].id)
  const [customText, setCustomText] = useState(PERSONA_PRESETS[0].proseDescription)
  const [isCompiling, setIsCompiling] = useState(false)
  const [activeTab, setActiveTab] = useState<"tiers" | "temperament" | "dialogue">("tiers")

  const currentPreset = PERSONA_PRESETS.find((p) => p.id === selectedPresetId) || PERSONA_PRESETS[0]

  const handleSelectPreset = (id: string) => {
    setSelectedPresetId(id)
    const p = PERSONA_PRESETS.find((item) => item.id === id)
    if (p) {
      setCustomText(p.proseDescription)
    }
  }

  const handleSimulateCompile = () => {
    setIsCompiling(true)
    setTimeout(() => {
      setIsCompiling(false)
    }, 400)
  }

  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pb-6 border-b border-black/[0.06]">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 bg-black/[0.04] px-2.5 py-1 rounded-full">
            Interactive Studio
          </span>
          <h3 className="text-2xl font-light tracking-tight mt-2 text-[#111]">
            Natural Language Persona Compiler
          </h3>
          <p className="text-xs text-black/45 mt-1">
            Type your friend's personality in plain English or select a curated companion archetype.
          </p>
        </div>

        {/* Preset Selector */}
        <div className="flex flex-wrap gap-2">
          {PERSONA_PRESETS.map((p) => (
            <button
              key={p.id}
              onClick={() => handleSelectPreset(p.id)}
              className={`px-3 py-1.5 rounded-lg text-xs tracking-wide transition-all ${
                selectedPresetId === p.id
                  ? "bg-[#111] text-white shadow-sm font-medium"
                  : "bg-black/[0.04] text-black/60 hover:bg-black/[0.08]"
              }`}
            >
              {p.name} · {p.relationshipRole.split(" ")[1]}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Natural Language Input */}
        <div className="lg:col-span-5 flex flex-col justify-between space-y-4">
          <div>
            <label className="block text-xs font-mono uppercase tracking-wider text-black/40 mb-2">
              Freeform Prose Description
            </label>
            <textarea
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              rows={6}
              className="w-full rounded-xl border border-black/[0.08] bg-[#fafaf8] p-4 text-xs sm:text-sm text-black/80 focus:outline-none focus:ring-1 focus:ring-black/20 font-sans leading-relaxed resize-none"
              placeholder="Describe your friend..."
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-[11px] text-black/40 font-mono">
              ~{customText.split(" ").length} words
            </span>
            <button
              onClick={handleSimulateCompile}
              disabled={isCompiling}
              className="px-5 py-2.5 bg-[#111] text-white text-xs font-medium rounded-xl hover:bg-[#333] transition-all flex items-center gap-2"
            >
              {isCompiling ? "Compiling..." : "Run Compiler Simulation"}
            </button>
          </div>

          <div className="bg-black/[0.02] border border-black/[0.05] rounded-xl p-3.5 text-xs text-black/50 leading-relaxed">
            <span className="font-medium text-black/70 block mb-1">Authentic Friction Guarantee:</span>
            The compiler infers communication bounds without smoothing over edgy descriptions or forcing sycophantic politeness.
          </div>
        </div>

        {/* Right Column: Inferred Tiers & Dry-Run */}
        <div className="lg:col-span-7 flex flex-col rounded-xl border border-black/[0.07] bg-[#fafaf8] p-5">
          {/* Sub-nav tabs */}
          <div className="flex gap-2 mb-4 border-b border-black/[0.06] pb-3">
            {[
              { id: "tiers", label: "3-Tier Constitution" },
              { id: "temperament", label: "Inferred Temperament" },
              { id: "dialogue", label: "Dry-Run Dialogue" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`px-3 py-1.5 rounded-md text-xs transition-colors ${
                  activeTab === tab.id
                    ? "bg-white text-black font-medium border border-black/[0.08] shadow-2xs"
                    : "text-black/40 hover:text-black/70"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab 1: 3-Tier Constitution */}
          {activeTab === "tiers" && (
            <div className="space-y-3 font-sans text-xs">
              <div className="p-3 bg-white rounded-lg border border-black/[0.06]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2 h-2 rounded-full bg-red-500/80" />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-black/40">Tier 0: Immutable Safety Floor</span>
                </div>
                <p className="text-black/60">Honesty, Privacy, Anti-Harm Boundaries (Hardcoded & Unoverridable)</p>
              </div>

              <div className="p-3 bg-white rounded-lg border border-black/[0.06]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2 h-2 rounded-full bg-blue-500/80" />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-black/40">Tier 1: Constitutional Temperament</span>
                </div>
                <p className="text-black/60">
                  Valence Base: {currentPreset.temperament.valenceBaseline} | Arousal Base: {currentPreset.temperament.arousalBaseline} | Dominance: {currentPreset.temperament.dominanceBaseline}
                </p>
              </div>

              <div className="p-3 bg-white rounded-lg border border-black/[0.06]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2 h-2 rounded-full bg-emerald-500/80" />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-black/40">Tier 2: Learned Lexicon & Adaptive Seeds</span>
                </div>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {currentPreset.memoryLexiconSeeds.map((t) => (
                    <span key={t} className="px-2 py-0.5 rounded bg-black/[0.04] text-black/70 text-[11px] font-mono">
                      #{t}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: Inferred Temperament */}
          {activeTab === "temperament" && (
            <div className="space-y-3 font-sans text-xs">
              {[
                { label: "Resting Valence (Positivity)", value: currentPreset.temperament.valenceBaseline, desc: "Baseline mood before conversational stimulus" },
                { label: "Resting Arousal (Energy / Pace)", value: currentPreset.temperament.arousalBaseline, desc: "Default conversational urgency & cadence" },
                { label: "Cortisol Sensitivity (Stress)", value: currentPreset.temperament.cortisolSensitivity, desc: "Reactivity to illogical claims or insults" },
                { label: "Dopamine Sensitivity (Reward)", value: currentPreset.temperament.dopamineSensitivity, desc: "Enthusiasm for shared accomplishments" },
              ].map((item) => (
                <div key={item.label} className="p-3 bg-white rounded-lg border border-black/[0.06]">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-medium text-black/80">{item.label}</span>
                    <span className="font-mono text-black/60 font-semibold">{item.value.toFixed(2)}</span>
                  </div>
                  <div className="w-full bg-black/[0.06] h-1.5 rounded-full overflow-hidden mb-1">
                    <div className="bg-[#111] h-full rounded-full" style={{ width: `${item.value * 100}%` }} />
                  </div>
                  <span className="text-[10px] text-black/40">{item.desc}</span>
                </div>
              ))}
            </div>
          )}

          {/* Tab 3: Dry-Run Dialogue */}
          {activeTab === "dialogue" && (
            <div className="space-y-3 text-xs flex-1 flex flex-col justify-center">
              <div className="bg-black/[0.04] p-3 rounded-lg text-black/80 max-w-[85%] self-start border border-black/[0.05]">
                <span className="font-mono text-[10px] uppercase text-black/40 block mb-1">You</span>
                "{currentPreset.sampleDialogue.user}"
              </div>

              <div className="bg-white p-3.5 rounded-lg text-black/85 max-w-[85%] self-end border border-black/[0.08] shadow-2xs">
                <span className="font-mono text-[10px] uppercase text-blue-600/70 block mb-1">{currentPreset.name} (Friend)</span>
                "{currentPreset.sampleDialogue.friendResponse}"
              </div>

              <div className="mt-4 pt-3 border-t border-black/[0.06] text-[11px] text-black/45 flex items-center justify-between">
                <span>Voice Profile: {currentPreset.voiceProfile.description}</span>
                <span className="text-emerald-700/80 font-medium">✓ Friction preserved</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
