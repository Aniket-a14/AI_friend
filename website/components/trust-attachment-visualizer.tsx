"use client"

import React, { useState } from "react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts"
import {
  updateFromAppraisal,
  initialRelationalState,
  trustOf,
  type RelationalState,
  type AppraisalDims,
  type RelationalCoefficients,
} from "@/lib/brain-math/trust-attachment"
import { PERSONA_PRESETS } from "@/lib/showcase-data"
import { inferTemperament } from "@/lib/persona-compiler-math"

interface HistoryPoint {
  turn: number
  trust: number
  attachment: number
  mood: number
}

function coefficientsForPreset(presetId: string): RelationalCoefficients {
  const preset = PERSONA_PRESETS.find((p) => p.id === presetId) ?? PERSONA_PRESETS[0]
  const { fields } = inferTemperament(preset.dimensions)
  return {
    alpha: fields.valenceDriftRate,
    beta: fields.arousalResponseRate,
    gamma: fields.dominanceStability,
    delta: fields.trustChangeRate,
    epsilon: fields.attachmentGrowthRate,
  }
}

export function TrustAttachmentVisualizer() {
  const [presetId, setPresetId] = useState(PERSONA_PRESETS[0].id)
  const [appraisal, setAppraisal] = useState<AppraisalDims>({ G: 0.5, RI: 0.3, N: 0.2, R: 0.5, A: 0.4, NA: 0.6 })
  const [state, setState] = useState<RelationalState>(initialRelationalState())
  const [history, setHistory] = useState<HistoryPoint[]>([
    { turn: 0, trust: trustOf(initialRelationalState()), attachment: initialRelationalState().attachment, mood: 0 },
  ])

  const coefficients = coefficientsForPreset(presetId)

  const advanceTurn = () => {
    const next = updateFromAppraisal(state, appraisal, coefficients)
    setState(next)
    setHistory((h) => [
      ...h,
      { turn: h.length, trust: trustOf(next), attachment: next.attachment, mood: next.mood },
    ])
  }

  const reset = () => {
    setState(initialRelationalState())
    setHistory([{ turn: 0, trust: trustOf(initialRelationalState()), attachment: initialRelationalState().attachment, mood: 0 }])
  }

  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pb-6 border-b border-black/[0.06]">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 bg-black/[0.04] px-2.5 py-1 rounded-full">
            Live Simulator
          </span>
          <h3 className="text-2xl font-light tracking-tight mt-2 text-[#111]">
            Trust & Attachment Over Time
          </h3>
          <p className="text-xs text-black/45 mt-1 max-w-2xl">
            Exact port of <code className="text-[11px]">AgentState.update_from_appraisal</code> — Marsh (1994)
            trust (benevolence/competence/integrity) and Bowlby attachment, both driven by the same appraisal
            that updates mood. Set the appraisal for one simulated turn, advance it, and watch the relationship move.
          </p>
        </div>
        <select
          value={presetId}
          onChange={(e) => setPresetId(e.target.value)}
          className="px-3 py-2 rounded-lg text-xs bg-black/[0.04] border border-black/[0.08] text-black/70"
        >
          {PERSONA_PRESETS.map((p) => (
            <option key={p.id} value={p.id}>{p.name} — trust/attachment rates</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-5 space-y-3">
          {(
            [
              { key: "G", label: "Goal Congruence", desc: "Did this help what you're trying to do?" },
              { key: "RI", label: "Relationship Impact", desc: "Did this feel like a moment between you two?" },
              { key: "N", label: "Novelty", desc: "How unexpected was it?" },
              { key: "R", label: "Relevance", desc: "How much did it matter right now?" },
              { key: "A", label: "Agency", desc: "How much control did you have over it?" },
              { key: "NA", label: "Norm Alignment", desc: "Did it match what's expected/appropriate?" },
            ] as const
          ).map((f) => (
            <div key={f.key} className="p-3 rounded-lg border border-black/[0.06] bg-[#fafaf8]">
              <div className="flex justify-between items-center mb-1">
                <span className="text-[11px] font-medium text-black/70">{f.label}</span>
                <span className="font-mono text-[11px] text-black/60">{appraisal[f.key].toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={-1}
                max={1}
                step={0.05}
                value={appraisal[f.key]}
                onChange={(e) => setAppraisal((a) => ({ ...a, [f.key]: parseFloat(e.target.value) }))}
                className="w-full accent-black h-1 bg-black/[0.08] rounded-lg cursor-pointer"
              />
              <span className="text-[9px] text-black/35">{f.desc}</span>
            </div>
          ))}
          <div className="flex gap-2 pt-1">
            <button
              onClick={advanceTurn}
              className="px-4 py-2 rounded-lg bg-[#111] text-white text-xs font-medium hover:bg-[#333] transition-colors"
            >
              Advance Turn →
            </button>
            <button
              onClick={reset}
              className="px-4 py-2 rounded-lg bg-black/[0.04] text-black/60 text-xs hover:bg-black/[0.08] transition-colors"
            >
              Reset
            </button>
          </div>
        </div>

        <div className="lg:col-span-7 rounded-xl border border-black/[0.07] bg-[#fafaf8] p-5">
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 block mb-3">
            {history.length - 1} turn{history.length - 1 === 1 ? "" : "s"} simulated
          </span>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={history} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
              <XAxis dataKey="turn" tick={{ fontSize: 10 }} />
              <YAxis domain={[-1, 1]} tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="trust" stroke="#2563eb" strokeWidth={2} dot={false} name="Trust (avg of 3)" />
              <Line type="monotone" dataKey="attachment" stroke="#db2777" strokeWidth={2} dot={false} name="Attachment" />
              <Line type="monotone" dataKey="mood" stroke="#059669" strokeWidth={2} dot={false} name="Mood" />
            </LineChart>
          </ResponsiveContainer>
          <div className="grid grid-cols-3 gap-3 mt-4 text-center">
            <div className="bg-white p-2.5 rounded-lg border border-black/[0.06]">
              <span className="text-[9px] text-black/40 uppercase block">Benevolence</span>
              <span className="font-mono text-sm">{state.trustBenevolence.toFixed(3)}</span>
            </div>
            <div className="bg-white p-2.5 rounded-lg border border-black/[0.06]">
              <span className="text-[9px] text-black/40 uppercase block">Competence</span>
              <span className="font-mono text-sm">{state.trustCompetence.toFixed(3)}</span>
            </div>
            <div className="bg-white p-2.5 rounded-lg border border-black/[0.06]">
              <span className="text-[9px] text-black/40 uppercase block">Integrity</span>
              <span className="font-mono text-sm">{state.trustIntegrity.toFixed(3)}</span>
            </div>
          </div>
          <p className="text-[11px] text-black/45 mt-3 leading-relaxed">
            Attachment grows slower than trust by construction: it's scaled by
            <code className="text-[10px]"> min(1, interaction_count/100)</code>, so even a friend who trusts
            you immediately still needs {state.interactionCount < 100 ? `${100 - state.interactionCount} more simulated turns` : "no more turns"} before
            that frequency term stops suppressing attachment growth.
          </p>
        </div>
      </div>
    </div>
  )
}
