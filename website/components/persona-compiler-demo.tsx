"use client"

import React, { useMemo, useState } from "react"
import { PERSONA_PRESETS } from "@/lib/showcase-data"
import { inferTemperament, DEFAULT_DIMENSIONS, type PersonaDimensions } from "@/lib/persona-compiler-math"

const DIMENSION_FIELDS: { key: keyof PersonaDimensions; label: string; min: number; max: number; low: string; high: string }[] = [
  { key: "warmth", label: "Warmth", min: -1, max: 1, low: "Cold", high: "Warm" },
  { key: "energy", label: "Energy", min: 0, max: 1, low: "Calm", high: "Excitable" },
  { key: "assertiveness", label: "Assertiveness", min: 0, max: 1, low: "Yielding", high: "Take-charge" },
  { key: "volatility", label: "Volatility", min: 0, max: 1, low: "Even-keeled", high: "Reactive" },
  { key: "resilience", label: "Resilience", min: 0, max: 1, low: "Dwells on things", high: "Bounces back" },
  { key: "opinionFirmness", label: "Opinion Firmness", min: 0, max: 1, low: "Easily swayed", high: "Stubborn" },
  { key: "opennessToTrust", label: "Openness to Trust", min: 0, max: 1, low: "Guarded", high: "Quick to trust" },
  { key: "warmthGrowth", label: "Warmth Growth", min: 0, max: 1, low: "Standoffish", high: "Quickly attached" },
  { key: "emotionalLingering", label: "Emotional Lingering", min: 0, max: 1, low: "Brief reactions", high: "Lingering reactions" },
]

export function PersonaCompilerDemo() {
  const [selectedPresetId, setSelectedPresetId] = useState(PERSONA_PRESETS[0].id)
  const [customText, setCustomText] = useState(PERSONA_PRESETS[0].proseDescription)
  const [dimensions, setDimensions] = useState<PersonaDimensions>(PERSONA_PRESETS[0].dimensions)
  const [activeTab, setActiveTab] = useState<"tiers" | "temperament" | "dialogue">("temperament")

  const currentPreset = PERSONA_PRESETS.find((p) => p.id === selectedPresetId) || PERSONA_PRESETS[0]

  // Recomputed synchronously on every slider change -- this is the real
  // deterministic math from backend/app/persona/compiler.py's
  // _infer_temperament, running live in the browser. No network call, no
  // fake delay: unlike the LLM-based prose->dimension step in the actual
  // product (not reproduced here), this half of the pipeline is pure
  // arithmetic and has nothing to wait on.
  const { fields, inferences } = useMemo(() => inferTemperament(dimensions), [dimensions])

  const handleSelectPreset = (id: string) => {
    setSelectedPresetId(id)
    const p = PERSONA_PRESETS.find((item) => item.id === id)
    if (p) {
      setCustomText(p.proseDescription)
      setDimensions(p.dimensions)
    }
  }

  const setDimension = (key: keyof PersonaDimensions, value: number) => {
    setDimensions((prev) => ({ ...prev, [key]: value }))
  }

  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pb-6 border-b border-black/[0.06]">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 bg-black/[0.04] px-2.5 py-1 rounded-full">
            Live Simulator
          </span>
          <h3 className="text-2xl font-light tracking-tight mt-2 text-[#111]">
            Persona Compiler: The Real Math
          </h3>
          <p className="text-xs text-black/45 mt-1 max-w-2xl">
            In the full system, an LLM reads your prose and scores it on 9 dimensions.
            Here you set those 9 scores directly with the sliders below and see the exact
            deterministic formula (<code className="text-[11px]">_infer_temperament</code>) that
            turns them into a persona — computed live in your browser, not simulated.
          </p>
        </div>

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
        {/* Left Column: Prose context + 9 dimension sliders */}
        <div className="lg:col-span-5 flex flex-col space-y-4">
          <div>
            <label className="block text-xs font-mono uppercase tracking-wider text-black/40 mb-2">
              Freeform Prose (context only — not scored here)
            </label>
            <textarea
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              rows={3}
              className="w-full rounded-xl border border-black/[0.08] bg-[#fafaf8] p-4 text-xs sm:text-sm text-black/80 focus:outline-none focus:ring-1 focus:ring-black/20 font-sans leading-relaxed resize-none"
              placeholder="Describe your friend..."
            />
          </div>

          <div className="space-y-2.5">
            {DIMENSION_FIELDS.map((f) => (
              <div key={f.key} className="p-2.5 rounded-lg border border-black/[0.06] bg-[#fafaf8]">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-[11px] font-medium text-black/70">{f.label}</span>
                  <span className="font-mono text-[11px] text-black/60">{dimensions[f.key].toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min={f.min}
                  max={f.max}
                  step={0.05}
                  value={dimensions[f.key]}
                  onChange={(e) => setDimension(f.key, parseFloat(e.target.value))}
                  className="w-full accent-black h-1 bg-black/[0.08] rounded-lg cursor-pointer"
                />
                <div className="flex justify-between text-[9px] text-black/35 mt-0.5">
                  <span>{f.low}</span>
                  <span>{f.high}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Inferred Tiers & Dry-Run */}
        <div className="lg:col-span-7 flex flex-col rounded-xl border border-black/[0.07] bg-[#fafaf8] p-5">
          <div className="flex gap-2 mb-4 border-b border-black/[0.06] pb-3">
            {[
              { id: "temperament", label: "Computed Temperament" },
              { id: "tiers", label: "3-Tier Constitution" },
              { id: "dialogue", label: "Preset Dry-Run" },
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

          {/* Tab: Computed Temperament -- the real live output */}
          {activeTab === "temperament" && (
            <div className="space-y-2 font-sans text-xs overflow-y-auto max-h-[420px] pr-1">
              {inferences.map((inf) => (
                <div key={inf.field} className="p-3 bg-white rounded-lg border border-black/[0.06]">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-medium text-black/80">{fieldLabel(inf.field)}</span>
                    <span className="font-mono text-black/60 font-semibold">{inf.value}</span>
                  </div>
                  <span className="text-[10px] text-black/40">{inf.reason}</span>
                </div>
              ))}
              <div className="text-[11px] text-black/45 bg-black/[0.02] border border-black/[0.05] rounded-lg p-3 mt-2">
                These {inferences.length} values are computed fresh on every slider move by the
                exact same formula as <code className="text-[10px]">backend/app/persona/compiler.py</code>.
                Try the Trust & Attachment demo to see how <code className="text-[10px]">trustChangeRate</code> and{" "}
                <code className="text-[10px]">attachmentGrowthRate</code> above then drive a relationship forward, turn by turn.
              </div>
            </div>
          )}

          {/* Tab: 3-Tier Constitution */}
          {activeTab === "tiers" && (
            <div className="space-y-3 font-sans text-xs">
              <div className="p-3 bg-white rounded-lg border border-black/[0.06]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2 h-2 rounded-full bg-red-500/80" />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-black/40">Tier 0: Immutable Safety Floor</span>
                </div>
                <p className="text-black/60">Honesty, privacy, and anti-harm boundaries — hardcoded, cannot be overridden by any persona description.</p>
              </div>

              <div className="p-3 bg-white rounded-lg border border-black/[0.06]">
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2 h-2 rounded-full bg-blue-500/80" />
                  <span className="font-mono text-[10px] uppercase tracking-wider text-black/40">Tier 1: Constitutional Temperament</span>
                </div>
                <p className="text-black/60">
                  Fixed at creation from the computed values on the left: baseline valence {fields.baselineValence}, arousal {fields.baselineArousal}, dominance {fields.baselineDominance}.
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

          {/* Tab: Dry-Run Dialogue (illustrative preset example, not computed from sliders) */}
          {activeTab === "dialogue" && (
            <div className="space-y-3 text-xs flex-1 flex flex-col justify-center">
              <p className="text-[10px] text-black/40 -mt-1 mb-1">
                Illustrative dialogue for {currentPreset.name}'s preset — written to match her character, not generated from the sliders.
              </p>
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

function fieldLabel(field: string): string {
  const labels: Record<string, string> = {
    baselineValence: "Baseline Valence",
    baselineArousal: "Baseline Arousal",
    baselineDominance: "Baseline Dominance",
    valenceDriftRate: "Valence Drift Rate",
    arousalResponseRate: "Arousal Response Rate",
    dominanceStability: "Dominance Stability",
    trustChangeRate: "Trust Change Rate",
    attachmentGrowthRate: "Attachment Growth Rate",
    moodDecayRate: "Mood Decay Rate",
    dopamineHalflifeS: "Dopamine Half-Life (s)",
    cortisolHalflifeS: "Cortisol Half-Life (s)",
    adrenalineHalflifeS: "Adrenaline Half-Life (s)",
    initialTrust: "Initial Trust",
    initialAttachment: "Initial Attachment",
  }
  return labels[field] ?? field
}
