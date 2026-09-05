"use client"

import React, { useState } from "react"
import {
  newDomainCalibration,
  recordObservation,
  evaluateDirective,
  type DomainCalibration,
  type MetacognitiveDirective,
} from "@/lib/brain-math/calibration"

const DIRECTIVE_STYLE: Record<MetacognitiveDirective, string> = {
  PROCEED: "bg-emerald-50 text-emerald-800 border-emerald-200",
  HEDGE: "bg-amber-50 text-amber-800 border-amber-200",
  ASK_CLARIFICATION: "bg-sky-50 text-sky-800 border-sky-200",
  VERIFY: "bg-orange-50 text-orange-800 border-orange-200",
  ABSTAIN: "bg-rose-50 text-rose-800 border-rose-200",
}

const KNOWN_LIMITATIONS = ["medical diagnosis", "legal advice", "financial guarantee"]

export function MetacognitiveAbstentionDemo() {
  const [domain, setDomain] = useState("general_conversation")
  const [rawConfidence, setRawConfidence] = useState(0.8)
  const [query, setQuery] = useState("")
  const [calibrations, setCalibrations] = useState<Record<string, DomainCalibration>>({
    general_conversation: newDomainCalibration("general_conversation"),
  })
  const [log, setLog] = useState<{ predicted: number; actual: 0 | 1 }[]>([])

  const calibration = calibrations[domain] ?? newDomainCalibration(domain)
  const { directive, calibrated } = evaluateDirective(KNOWN_LIMITATIONS, calibrations, domain, rawConfidence, query)

  const submitOutcome = (actual: 0 | 1) => {
    const updated = recordObservation(calibration, rawConfidence, actual)
    setCalibrations((c) => ({ ...c, [domain]: updated }))
    setLog((l) => [...l, { predicted: rawConfidence, actual }].slice(-12))
  }

  const reset = () => {
    setCalibrations({ [domain]: newDomainCalibration(domain) })
    setLog([])
  }

  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm">
      <div className="mb-6 pb-6 border-b border-black/[0.06]">
        <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 bg-black/[0.04] px-2.5 py-1 rounded-full">
          Live Simulator
        </span>
        <h3 className="text-2xl font-light tracking-tight mt-2 text-[#111]">
          Metacognitive Abstention
        </h3>
        <p className="text-xs text-black/45 mt-1 max-w-2xl">
          1:1 port of <code className="text-[11px]">backend/app/cognitive/calibration.py</code> — the model's own stated
          confidence is never trusted directly. It's discounted by an observed Brier score and mapped to one of five
          deterministic directives.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-6 space-y-4">
          <div className="p-3 rounded-lg border border-black/[0.06] bg-[#fafaf8]">
            <div className="flex justify-between text-[11px] mb-1"><span className="font-medium text-black/70">Raw Confidence</span><span className="font-mono">{rawConfidence.toFixed(2)}</span></div>
            <input type="range" min={0} max={1} step={0.01} value={rawConfidence} onChange={(e) => setRawConfidence(parseFloat(e.target.value))} className="w-full accent-black h-1" />
          </div>
          <div className="p-3 rounded-lg border border-black/[0.06] bg-[#fafaf8]">
            <label className="text-[11px] font-medium text-black/70 block mb-1.5">Query text (try mentioning "medical diagnosis")</label>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="What the user asked..."
              className="w-full rounded-lg border border-black/[0.08] bg-white px-3 py-2 text-xs"
            />
          </div>
          <div className="p-3 rounded-lg border border-black/[0.06] bg-[#fafaf8]">
            <label className="text-[11px] font-medium text-black/70 block mb-1.5">Domain</label>
            <select
              value={domain}
              onChange={(e) => {
                const d = e.target.value
                setDomain(d)
                setCalibrations((c) => (c[d] ? c : { ...c, [d]: newDomainCalibration(d) }))
              }}
              className="w-full rounded-lg border border-black/[0.08] bg-white px-3 py-2 text-xs"
            >
              <option value="general_conversation">general_conversation</option>
              <option value="factual_recall">factual_recall</option>
              <option value="planning">planning</option>
            </select>
          </div>

          <div className={`rounded-xl border p-5 text-center ${DIRECTIVE_STYLE[directive]}`}>
            <span className="text-[10px] font-mono uppercase tracking-widest block mb-1">Directive</span>
            <span className="text-2xl font-medium">{directive}</span>
            <p className="text-xs mt-1 opacity-80">calibrated confidence: {calibrated.toFixed(3)}</p>
          </div>
        </div>

        <div className="lg:col-span-6 rounded-xl border border-black/[0.07] bg-[#fafaf8] p-5">
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 block mb-3">
            Feed the Calibrator (domain: {domain})
          </span>
          <p className="text-[11px] text-black/50 mb-3 leading-relaxed">
            Submit whether a prediction at the current raw confidence would have actually been right or wrong.
            Watch the calibrated confidence above shift as the Brier score accumulates — this is what "learning
            not to trust your own confidence in a domain" looks like as arithmetic.
          </p>
          <div className="flex gap-2 mb-4">
            <button onClick={() => submitOutcome(1)} className="flex-1 px-3 py-2 rounded-lg bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700">
              It was right
            </button>
            <button onClick={() => submitOutcome(0)} className="flex-1 px-3 py-2 rounded-lg bg-rose-600 text-white text-xs font-medium hover:bg-rose-700">
              It was wrong
            </button>
            <button onClick={reset} className="px-3 py-2 rounded-lg bg-black/[0.06] text-black/60 text-xs hover:bg-black/[0.1]">
              Reset
            </button>
          </div>
          <div className="bg-white rounded-lg border border-black/[0.06] p-3 space-y-1 max-h-40 overflow-y-auto">
            {log.length === 0 && <p className="text-[11px] text-black/35">No observations yet.</p>}
            {log.map((entry, i) => (
              <div key={i} className="flex justify-between text-[11px] font-mono text-black/60">
                <span>predicted {entry.predicted.toFixed(2)}</span>
                <span>{entry.actual === 1 ? "✓ correct" : "✗ wrong"}</span>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3 mt-4 text-center">
            <div className="bg-white p-2.5 rounded-lg border border-black/[0.06]">
              <span className="text-[9px] text-black/40 uppercase block">Brier Score</span>
              <span className="font-mono text-sm">{calibration.brierScore.toFixed(3)}</span>
            </div>
            <div className="bg-white p-2.5 rounded-lg border border-black/[0.06]">
              <span className="text-[9px] text-black/40 uppercase block">Samples</span>
              <span className="font-mono text-sm">{calibration.sampleCount}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
