"use client"

import React, { useState } from "react"
import { updateKnownConcepts, extractBeliefDiscrepancies } from "@/lib/brain-math/theory-of-mind"

// Scripted mini-conversation. The concept-tracking below runs the real
// deterministic algorithm on this text live; the "ground truth" and belief
// fields are illustrative scenario data, not computed from anything (see
// the honesty note in the docs -- tom.py itself doesn't infer beliefs, it
// only tracks concepts and diffs beliefs you already have against a truth
// table you already have).
const SCRIPT: { line: string; belief?: [string, string] }[] = [
  { line: "I've been getting into rock climbing lately, it's honestly the best part of my week." },
  { line: "My belay partner Jordan says the new gym downtown has way harder routes than the old one." },
  { line: "I think the gym closes at 11pm on weekdays, so I usually go around 8.", belief: ["gym_closing_time", "11pm"] },
  { line: "Jordan mentioned they're training for an outdoor trip to Yosemite next spring." },
  { line: "I heard the membership price went up to $95 a month recently.", belief: ["membership_price", "$95/month"] },
]

const GROUND_TRUTH: Record<string, string> = {
  gym_closing_time: "10pm",
  membership_price: "$110/month",
}

export function TheoryOfMindDemo() {
  const [step, setStep] = useState(0)
  const [concepts, setConcepts] = useState<string[]>([])
  const [beliefs, setBeliefs] = useState<Record<string, string>>({})
  const [revealed, setRevealed] = useState(false)

  const advance = () => {
    if (step >= SCRIPT.length) return
    const entry = SCRIPT[step]
    setConcepts((c) => updateKnownConcepts(c, entry.line))
    if (entry.belief) {
      setBeliefs((b) => ({ ...b, [entry.belief![0]]: entry.belief![1] }))
    }
    setStep((s) => s + 1)
  }

  const reset = () => {
    setStep(0)
    setConcepts([])
    setBeliefs({})
    setRevealed(false)
  }

  const discrepancies = extractBeliefDiscrepancies(beliefs, GROUND_TRUTH)

  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm">
      <div className="mb-6 pb-6 border-b border-black/[0.06]">
        <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 bg-black/[0.04] px-2.5 py-1 rounded-full">
          Live Simulator
        </span>
        <h3 className="text-2xl font-light tracking-tight mt-2 text-[#111]">
          Theory of Mind: What You Know vs. What's True
        </h3>
        <p className="text-xs text-black/45 mt-1 max-w-2xl">
          The concept tracker below runs the real, deterministic <code className="text-[11px]">update_known_concepts</code> and{" "}
          <code className="text-[11px]">extract_belief_discrepancies</code> from <code className="text-[11px]">backend/app/cognitive/tom.py</code> —
          no LLM, just regex and dict diffing. The scripted conversation and "ground truth" are illustrative scenario data.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-6 space-y-3">
          {SCRIPT.slice(0, step).map((entry, i) => (
            <div key={i} className="bg-black/[0.04] p-3 rounded-lg text-xs text-black/80 border border-black/[0.05]">
              "{entry.line}"
            </div>
          ))}
          <div className="flex gap-2 pt-2">
            {step < SCRIPT.length ? (
              <button onClick={advance} className="px-4 py-2 rounded-lg bg-[#111] text-white text-xs font-medium hover:bg-[#333]">
                Next line →
              </button>
            ) : (
              <button onClick={() => setRevealed(true)} className="px-4 py-2 rounded-lg bg-[#111] text-white text-xs font-medium hover:bg-[#333]">
                Reveal ground truth
              </button>
            )}
            <button onClick={reset} className="px-4 py-2 rounded-lg bg-black/[0.04] text-black/60 text-xs hover:bg-black/[0.08]">
              Reset
            </button>
          </div>
        </div>

        <div className="lg:col-span-6 rounded-xl border border-black/[0.07] bg-[#fafaf8] p-5 space-y-4">
          <div>
            <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 block mb-2">
              Known Concepts ({concepts.length}) — live, real algorithm
            </span>
            <div className="flex flex-wrap gap-1.5 max-h-28 overflow-y-auto">
              {concepts.length === 0 && <span className="text-[11px] text-black/35">Nothing tracked yet.</span>}
              {concepts.map((c) => (
                <span key={c} className="px-2 py-0.5 rounded bg-white border border-black/[0.06] text-[11px] font-mono text-black/70">
                  {c}
                </span>
              ))}
            </div>
          </div>

          {revealed && (
            <div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 block mb-2">
                Belief Discrepancies — real diff, illustrative data
              </span>
              {Object.keys(discrepancies).length === 0 ? (
                <p className="text-[11px] text-black/45">No discrepancies found in this run.</p>
              ) : (
                <div className="space-y-2">
                  {Object.entries(discrepancies).map(([concept, d]) => (
                    <div key={concept} className="bg-white rounded-lg border border-rose-200 p-3 text-xs">
                      <span className="font-mono text-[10px] text-black/40 block mb-1">{concept}</span>
                      <span className="text-rose-700">You said: {d.userBelief}</span>
                      <span className="block text-emerald-700">Actually: {d.groundTruth}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
