"use client"

import React, { useState } from "react"

const VOICE_VARIANTS = [
  {
    id: "calm",
    name: "Calm / Grounded",
    affect: "Low Arousal, Positive Valence",
    pauseScale: "1.25x (Relaxed cadence)",
    description: "Generous inter-phrase pauses and lowered pitch variance, suitable for deep reflection and late-night conversation.",
    sampleText: "Take your time. There's no rush to figure this out tonight.",
  },
  {
    id: "warm",
    name: "Warm / Affectionate",
    affect: "High Valence, Moderate Arousal",
    pauseScale: "1.0x (Standard cadence)",
    description: "Expanded acoustic warmth with melodic pitch contours and rapid empathetic alignment.",
    sampleText: "I'm genuinely glad that worked out for you. You earned that win.",
  },
  {
    id: "concerned",
    name: "Concerned / Attentive",
    affect: "Negative Valence, High Arousal",
    pauseScale: "0.85x (Urgent cadence)",
    description: "Tighter pauses and sharper speech onset, reflecting attentiveness to distress or critical bugs.",
    sampleText: "Hold on — that doesn't sound right at all. Are you sure that went through?",
  },
  {
    id: "excited",
    name: "Excited / Energized",
    affect: "High Valence, High Arousal",
    pauseScale: "0.75x (Rapid tempo)",
    description: "Fast tempo, dynamic pitch peaks, and minimized pause lengths when exploring an intriguing breakthrough.",
    sampleText: "That's incredible! Send over the link right now, I have to see this.",
  },
]

// No audio plays here yet -- see /roadmap. What's shown is accurate: the
// real reference-clip selection and pause-scale parameters the voice agent
// actually uses per affect register, just without a rendered clip attached.
export function VoiceShowcase() {
  const [activeVariantId, setActiveVariantId] = useState(VOICE_VARIANTS[0].id)
  const activeVariant = VOICE_VARIANTS.find((v) => v.id === activeVariantId) || VOICE_VARIANTS[0]

  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pb-6 border-b border-black/[0.06]">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 bg-black/[0.04] px-2.5 py-1 rounded-full">
            Reference Parameters — No Audio Yet
          </span>
          <h3 className="text-2xl font-light tracking-tight mt-2 text-[#111]">
            Emotional Voice Cloning & Prosody
          </h3>
          <p className="text-xs text-black/45 mt-1">
            The real per-affect reference-clip and pause-scale mapping the voice agent uses. No rendered
            audio is wired up on the website yet — see <a href="/roadmap" className="underline">the roadmap</a>.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {VOICE_VARIANTS.map((v) => (
            <button
              key={v.id}
              onClick={() => setActiveVariantId(v.id)}
              className={`px-3 py-1.5 rounded-lg text-xs tracking-wide transition-all ${
                activeVariantId === v.id
                  ? "bg-[#111] text-white shadow-sm"
                  : "bg-black/[0.04] text-black/60 hover:bg-black/[0.08]"
              }`}
            >
              {v.name.split(" ")[0]}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
        <div className="lg:col-span-6 rounded-xl border border-black/[0.08] bg-[#fafaf8] p-6 flex flex-col items-center justify-center text-center space-y-4">
          <span className="font-mono text-[10px] uppercase tracking-widest text-black/35">Sample line for this register</span>
          <div className="text-sm text-black/70 font-sans italic max-w-sm">
            "{activeVariant.sampleText}"
          </div>
        </div>

        <div className="lg:col-span-6 space-y-3 font-sans text-xs">
          <div className="p-3.5 bg-white rounded-lg border border-black/[0.06]">
            <span className="font-mono text-[10px] uppercase text-black/35 block mb-0.5">Affect Parameter Space</span>
            <span className="font-medium text-black/80">{activeVariant.affect}</span>
          </div>

          <div className="p-3.5 bg-white rounded-lg border border-black/[0.06]">
            <span className="font-mono text-[10px] uppercase text-black/35 block mb-0.5">Pause Scaling Bias</span>
            <span className="font-medium text-black/80">{activeVariant.pauseScale}</span>
          </div>

          <div className="p-3.5 bg-white rounded-lg border border-black/[0.06]">
            <span className="font-mono text-[10px] uppercase text-black/35 block mb-0.5">Acoustic Characteristic</span>
            <p className="text-black/60 leading-relaxed mt-0.5">{activeVariant.description}</p>
          </div>

          <div className="flex items-center justify-between text-[11px] text-black/40 pt-2 border-t border-black/[0.04]">
            <span>Engine: GPT-SoVITS (32,000 Hz)</span>
            <span className="text-emerald-700/80 font-medium">Barge-in reflex: &lt; 1ms (0.099 ms validated)</span>
          </div>
        </div>
      </div>
    </div>
  )
}
