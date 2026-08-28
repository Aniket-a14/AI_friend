"use client"

import { useEffect, useRef, useState } from "react"

const AGENTS = [
  {
    label: "BRAIN AGENT",
    title: "The cognitive core",
    desc: "Runs the full turn: appraises what happened, updates PAD affect and the endocrine layer, decides how to respond, and streams the reply through your local Ollama model.",
    stats: [{ v: "Python", l: "runtime" }, { v: "Ollama", l: "LLM backend" }],
  },
  {
    label: "VOICE AGENT",
    title: "Speech, physically synthesized",
    desc: "Renders every reply through one self-hosted, cloned voice — no fallback to a different voice. Pauses, ducking, and prosody are real PCM sample manipulation, not text markers.",
    stats: [{ v: "Rust", l: "runtime" }, { v: "GPT-SoVITS", l: "synthesis" }],
  },
  {
    label: "STT AGENT",
    title: "Dual-path listening",
    desc: "A fast speculative path classifies intent and emotion mid-sentence for natural barge-in; a slower accurate path produces the final transcript once you're done talking.",
    stats: [{ v: "whisper.cpp", l: "accurate path" }, { v: "SenseVoice", l: "fast path" }],
  },
  {
    label: "SUBCONSCIOUS AGENT",
    title: "Reflection, between turns",
    desc: "Consolidates memory, decays what's no longer relevant, and can reach out to you unprompted — a friend that thinks about you when you're not talking to it.",
    stats: [{ v: "Neo4j", l: "knowledge graph" }, { v: "ACT-R", l: "memory decay" }],
  },
]

const STICKY_TOP   = 80   // matches top: 80px on first card
const STICKY_STEP  = 16   // each card stacks 16px lower
const SCALE_STEP   = 0.04 // scale reduction per card stacked on top
const OFFSET_STEP  = 8    // px pushed down per card stacked on top

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center px-3 py-1 rounded-full text-[11px] tracking-widest font-sans text-black/40 bg-black/[0.04]">
      {children}
    </span>
  )
}

export function StackingAgentCards() {
  const cardRefs = useRef<(HTMLDivElement | null)[]>([])
  // depth[i] = 0..N how many cards are currently stacked on top of card i
  const [depth, setDepth] = useState<number[]>(AGENTS.map(() => 0))

  useEffect(() => {
    function onScroll() {
      const nextDepth = AGENTS.map((_, i) => {
        // Count how many cards j > i are currently in sticky position (i.e. have scrolled past card i)
        let count = 0
        for (let j = i + 1; j < AGENTS.length; j++) {
          const el = cardRefs.current[j]
          if (!el) continue
          const rect = el.getBoundingClientRect()
          const stickyTopJ = STICKY_TOP + j * STICKY_STEP
          // Card j is "on top of" card i when it has reached its sticky position
          if (rect.top <= stickyTopJ + 2) count++
        }
        return count
      })
      setDepth(nextDepth)
    }

    window.addEventListener("scroll", onScroll, { passive: true })
    onScroll()
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  return (
    <div className="flex flex-col" style={{ perspective: "1400px", perspectiveOrigin: "50% 0%" }}>
      {AGENTS.map((agent, i) => {
        const d         = depth[i]
        const scale     = 1 - d * SCALE_STEP
        const translateY = d * OFFSET_STEP

        return (
          <div
            key={agent.label}
            ref={el => { cardRefs.current[i] = el }}
            className="sticky mb-4"
            style={{ top: `${STICKY_TOP + i * STICKY_STEP}px`, zIndex: 10 + i }}
          >
            <div
              style={{
                transform:      `scale(${scale}) translateY(${translateY}px)`,
                transformOrigin: "top center",
                transition:     "transform 0.3s cubic-bezier(0.16,1,0.3,1)",
                willChange:     "transform",
              }}
            >
              <div className="group relative bg-[#faf9f7] rounded-2xl border border-black/[0.07] overflow-hidden cursor-pointer">

                {/* Text content */}
                <div className="relative z-10 p-8">
                  <div className="md:max-w-xl">
                    <div className="flex items-start justify-between mb-6">
                      <Tag>{agent.label}</Tag>
                    </div>
                    <h3 className="text-xl font-light mb-3">{agent.title}</h3>
                    <p className="text-sm text-black/45 leading-relaxed mb-8">{agent.desc}</p>
                  </div>
                  <div className="flex gap-8 pt-6 border-t border-black/[0.06]">
                    {agent.stats.map(s => (
                      <div key={s.l}>
                        <div className="text-2xl font-light">{s.v}</div>
                        <div className="text-[11px] text-black/35 tracking-widest mt-0.5">{s.l}</div>
                      </div>
                    ))}
                  </div>
                </div>

              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
