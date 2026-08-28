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

export function VoiceShowcase() {
  const [activeVariantId, setActiveVariantId] = useState(VOICE_VARIANTS[0].id)
  const [isPlaying, setIsPlaying] = useState(false)

  const activeVariant = VOICE_VARIANTS.find((v) => v.id === activeVariantId) || VOICE_VARIANTS[0]

  const handleTogglePlay = () => {
    setIsPlaying(true)
    setTimeout(() => setIsPlaying(false), 2500)
  }

  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pb-6 border-b border-black/[0.06]">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 bg-black/[0.04] px-2.5 py-1 rounded-full">
            Acoustic Physical Modeling
          </span>
          <h3 className="text-2xl font-light tracking-tight mt-2 text-[#111]">
            Emotional Voice Cloning & Prosody
          </h3>
          <p className="text-xs text-black/45 mt-1">
            Real 32kHz neural voice rendering dynamically shaped by affective state and pause bias.
          </p>
        </div>

        {/* Emotion Switcher */}
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
        {/* Visual Waveform & Player on Left */}
        <div className="lg:col-span-6 rounded-xl border border-black/[0.08] bg-[#fafaf8] p-6 flex flex-col items-center justify-center text-center space-y-4">
          <div className="w-16 h-16 rounded-full bg-white border border-black/[0.08] flex items-center justify-center shadow-xs">
            <button
              onClick={handleTogglePlay}
              className="w-12 h-12 rounded-full bg-[#111] text-white flex items-center justify-center hover:bg-[#333] transition-colors"
            >
              {isPlaying ? "■" : "▶"}
            </button>
          </div>

          {/* Animated Waveform Visualization */}
          <div className="flex items-center gap-1 h-12 px-4 py-2 w-full justify-center">
            {[24, 48, 16, 64, 32, 80, 40, 96, 50, 72, 36, 60, 20, 84, 44, 28, 56, 38, 70, 30].map((h, i) => (
              <span
                key={i}
                className="w-1 bg-[#111] rounded-full transition-all duration-300"
                style={{
                  height: isPlaying ? `${Math.max(8, (h * (i % 3 + 1)) % 48)}px` : "6px",
                  opacity: isPlaying ? 0.85 : 0.2,
                }}
              />
            ))}
          </div>

          <div className="text-xs text-black/60 font-sans italic max-w-sm">
            "{activeVariant.sampleText}"
          </div>
        </div>

        {/* Technical Specification on Right */}
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
            <span className="text-emerald-700/80 font-medium">Barge-in latency target: &lt; 150ms</span>
          </div>
        </div>
      </div>
    </div>
  )
}

