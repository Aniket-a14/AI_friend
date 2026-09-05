"use client"

import React, { useState } from "react"
import { MobileNav } from "@/components/mobile-nav"
import { SiteFooter } from "@/components/site-footer"
import { PersonaCompilerDemo } from "@/components/persona-compiler-demo"
import { CognitiveTurnFlow } from "@/components/cognitive-turn-flow"
import { EndocrineSimulator } from "@/components/endocrine-simulator"
import { VoiceShowcase } from "@/components/voice-showcase"
import { TrustAttachmentVisualizer } from "@/components/trust-attachment-visualizer"
import { MemoryActivationVisualizer } from "@/components/memory-activation-visualizer"
import { MetacognitiveAbstentionDemo } from "@/components/metacognitive-abstention-demo"
import { TheoryOfMindDemo } from "@/components/theory-of-mind-demo"

type Tab = "endocrine" | "turn" | "memory" | "persona" | "trust" | "metacognition" | "tom" | "voice"

export default function PlaygroundPage() {
  const [activeTab, setActiveTab] = useState<Tab>("endocrine")

  const tabs: { id: Tab; label: string }[] = [
    { id: "endocrine", label: "1. Endocrine & LLM Physics" },
    { id: "turn", label: "2. 7-Stage Cognitive Turn" },
    { id: "memory", label: "3. Memory Activation & Decay" },
    { id: "persona", label: "4. Persona Studio & Compiler" },
    { id: "trust", label: "5. Trust & Attachment" },
    { id: "metacognition", label: "6. Metacognitive Abstention" },
    { id: "tom", label: "7. Theory of Mind" },
    { id: "voice", label: "8. Acoustic & Prosody Reference" },
  ]

  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />

      <main className="max-w-6xl mx-auto px-6 md:px-12 pt-36 pb-24">
        <div className="mb-10 max-w-3xl">
          <div className="mb-3 inline-flex items-center gap-2 font-mono text-xs text-black/40">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Developer Sandbox — every tab below computes live, in your browser
          </div>
          <h1 className="text-4xl sm:text-5xl font-light tracking-tight text-[#111] mb-4" style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}>
            Interactive Cognitive Playground
          </h1>
          <p className="text-sm sm:text-base text-black/50 leading-relaxed">
            Real formulas ported from the actual backend — endocrine sampling physics, the cognitive turn
            tracer, ACT-R memory decay, the persona compiler's scoring math, Marsh trust/Bowlby attachment,
            metacognitive calibration, and theory-of-mind concept tracking. None of these call your live
            instance (there isn't a public one to call) — see each tab's own note for exactly what's real
            math versus illustrative scenario data. Things that aren't built yet live on{" "}
            <a href="/roadmap" className="underline">the roadmap page</a>, not here.
          </p>
        </div>

        <div className="flex flex-wrap gap-2 mb-8 border-b border-black/[0.08] pb-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 rounded-xl text-xs transition-all ${
                activeTab === tab.id
                  ? "bg-[#111] text-white shadow-xs font-medium"
                  : "bg-white text-black/60 border border-black/[0.06] hover:bg-[#fafaf8]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="space-y-8">
          {activeTab === "endocrine" && <EndocrineSimulator />}
          {activeTab === "turn" && <CognitiveTurnFlow />}
          {activeTab === "memory" && <MemoryActivationVisualizer />}
          {activeTab === "persona" && <PersonaCompilerDemo />}
          {activeTab === "trust" && <TrustAttachmentVisualizer />}
          {activeTab === "metacognition" && <MetacognitiveAbstentionDemo />}
          {activeTab === "tom" && <TheoryOfMindDemo />}
          {activeTab === "voice" && <VoiceShowcase />}
        </div>
      </main>

      <SiteFooter />
    </div>
  )
}
