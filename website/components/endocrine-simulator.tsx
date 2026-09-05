"use client"

import React, { useState } from "react"

export function EndocrineSimulator() {
  const [cortisol, setCortisol] = useState(0.3) // Stress / Caution [0..1]
  const [dopamine, setDopamine] = useState(0.5) // Reward / Enthusiasm [0..1]
  const [fatigue, setFatigue] = useState(0.2)   // Exhaustion [0..1]

  // Exact formulas from backend/app/cognitive/action.py::_compute_endocrine_options:
  // temperature is cortisol-only, top_p is dopamine-only (no cross-coupling in the
  // real mapping), num_predict is fatigue-only, bounded [100, 250].
  const calculatedTemperature = Math.max(0.0, Math.min(1.0, (0.9 - cortisol * 0.6))).toFixed(2)
  const calculatedTopP = Math.max(0.0, Math.min(1.0, (0.70 + dopamine * 0.25))).toFixed(2)
  const calculatedMaxTokens = Math.round(Math.max(100, Math.min(250, 250 - fatigue * 150)))
  // Illustrative only -- action.py has no speaking-rate mapping; real tempo
  // entrainment lives separately in the Rust voice agent's pause_bias/tempo_wpm.
  const speakingRateWpm = Math.round(140 + dopamine * 40 - fatigue * 30 + cortisol * 15)

  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pb-6 border-b border-black/[0.06]">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 bg-black/[0.04] px-2.5 py-1 rounded-full">
            Affective Modulation & Sampling Physics
          </span>
          <h3 className="text-2xl font-light tracking-tight mt-2 text-[#111]">
            Endocrine Parameter Modulator
          </h3>
          <p className="text-xs text-black/45 mt-1">
            Adjust simulated neurochemicals to see how internal affective states dynamically reshape LLM generation.
          </p>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => { setCortisol(0.85); setDopamine(0.15); setFatigue(0.4); }}
            className="px-3 py-1.5 rounded-lg text-xs bg-red-50 text-red-700 border border-red-200/60 hover:bg-red-100 transition-colors"
          >
            Simulate Stress
          </button>
          <button
            onClick={() => { setCortisol(0.1); setDopamine(0.9); setFatigue(0.1); }}
            className="px-3 py-1.5 rounded-lg text-xs bg-emerald-50 text-emerald-700 border border-emerald-200/60 hover:bg-emerald-100 transition-colors"
          >
            Simulate Flow
          </button>
          <button
            onClick={() => { setCortisol(0.3); setDopamine(0.5); setFatigue(0.2); }}
            className="px-3 py-1.5 rounded-lg text-xs bg-black/[0.04] text-black/60 hover:bg-black/[0.08] transition-colors"
          >
            Reset
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
        {/* Sliders on Left */}
        <div className="lg:col-span-6 space-y-5">
          {/* Cortisol Slider */}
          <div className="p-4 rounded-xl border border-black/[0.06] bg-[#fafaf8]">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-medium text-black/80 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-rose-500" />
                Cortisol (Stress / Vigilance)
              </span>
              <span className="font-mono text-xs text-rose-700 font-semibold">{cortisol.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={cortisol}
              onChange={(e) => setCortisol(parseFloat(e.target.value))}
              className="w-full accent-rose-600 h-1.5 bg-black/[0.08] rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-black/40 mt-1.5">
              <span>Calm / Relaxed</span>
              <span>Half-life: 4500s</span>
              <span>High Alert / Defensive</span>
            </div>
          </div>

          {/* Dopamine Slider */}
          <div className="p-4 rounded-xl border border-black/[0.06] bg-[#fafaf8]">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-medium text-black/80 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                Dopamine (Reward / Engagement)
              </span>
              <span className="font-mono text-xs text-amber-700 font-semibold">{dopamine.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={dopamine}
              onChange={(e) => setDopamine(parseFloat(e.target.value))}
              className="w-full accent-amber-500 h-1.5 bg-black/[0.08] rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-black/40 mt-1.5">
              <span>Neutral</span>
              <span>Half-life: 90s</span>
              <span>High Enthusiasm</span>
            </div>
          </div>

          {/* Fatigue Slider */}
          <div className="p-4 rounded-xl border border-black/[0.06] bg-[#fafaf8]">
            <div className="flex justify-between items-center mb-2">
              <span className="text-xs font-medium text-black/80 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-slate-500" />
                Physical Fatigue (Turn Fatigue)
              </span>
              <span className="font-mono text-xs text-slate-700 font-semibold">{fatigue.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={fatigue}
              onChange={(e) => setFatigue(parseFloat(e.target.value))}
              className="w-full accent-slate-600 h-1.5 bg-black/[0.08] rounded-lg cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-black/40 mt-1.5">
              <span>Energized</span>
              <span>Accumulates over turns</span>
              <span>Exhausted</span>
            </div>
          </div>
        </div>

        {/* Calculated Output Values on Right */}
        <div className="lg:col-span-6 rounded-xl border border-black/[0.08] bg-[#fafaf8] p-6 space-y-4">
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 block border-b border-black/[0.06] pb-2">
            Inferred LLM Sampling & Acoustic Parameters
          </span>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white p-3.5 rounded-lg border border-black/[0.06]">
              <span className="text-[10px] text-black/40 uppercase block mb-1 font-mono">LLM Temperature</span>
              <span className="text-2xl font-light font-mono text-[#111]">{calculatedTemperature}</span>
              <p className="text-[10px] text-black/45 mt-1 leading-tight">
                {parseFloat(calculatedTemperature) < 0.45 ? "Cautious & Focused" : "Creative & Broad"}
              </p>
            </div>

            <div className="bg-white p-3.5 rounded-lg border border-black/[0.06]">
              <span className="text-[10px] text-black/40 uppercase block mb-1 font-mono">Sampling Top-P</span>
              <span className="text-2xl font-light font-mono text-[#111]">{calculatedTopP}</span>
              <p className="text-[10px] text-black/45 mt-1 leading-tight">
                {parseFloat(calculatedTopP) > 0.85 ? "Diverse Vocabulary" : "Tight Lexical Selection"}
              </p>
            </div>

            <div className="bg-white p-3.5 rounded-lg border border-black/[0.06]">
              <span className="text-[10px] text-black/40 uppercase block mb-1 font-mono">Max Response Tokens</span>
              <span className="text-2xl font-light font-mono text-[#111]">{calculatedMaxTokens}</span>
              <p className="text-[10px] text-black/45 mt-1 leading-tight">
                {calculatedMaxTokens < 200 ? "Brief & Direct Speech" : "Expansive Explanations"}
              </p>
            </div>

            <div className="bg-white p-3.5 rounded-lg border border-black/[0.06]">
              <span className="text-[10px] text-black/40 uppercase block mb-1 font-mono">Estimated Tempo</span>
              <span className="text-2xl font-light font-mono text-[#111]">{speakingRateWpm} <span className="text-xs text-black/40">WPM</span></span>
              <p className="text-[10px] text-black/45 mt-1 leading-tight">
                Physical speech pacing & pause bias
              </p>
            </div>
          </div>

          <div className="text-[11px] text-black/50 bg-white p-3 rounded-lg border border-black/[0.05] leading-relaxed">
            <strong>Affective Independence:</strong> Phasic bursts decay according to calibrated half-lives, allowing the agent to be stressed by an urgent task while enthusiastic about solving it.
          </div>
        </div>
      </div>
    </div>
  )
}
