"use client"

import React, { useState } from "react"
import { MobileNav } from "@/components/mobile-nav"
import { SiteFooter } from "@/components/site-footer"
import { PersonaCompilerDemo } from "@/components/persona-compiler-demo"
import { CognitiveTurnFlow } from "@/components/cognitive-turn-flow"
import { EndocrineSimulator } from "@/components/endocrine-simulator"
import { VoiceShowcase } from "@/components/voice-showcase"
import { ComingSoonOverlay } from "@/components/coming-soon-overlay"

export default function PlaygroundPage() {
  const [activeTab, setActiveTab] = useState<"persona" | "turn" | "endocrine" | "voice" | "webgpu" | "memory_graph">("endocrine")

  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />

      <main className="max-w-6xl mx-auto px-6 md:px-12 pt-36 pb-24">
        {/* Header */}
        <div className="mb-10 max-w-3xl">
          <div className="mb-3 inline-flex items-center gap-2 font-mono text-xs text-black/40">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Developer Sandbox
          </div>
          <h1 className="text-4xl sm:text-5xl font-light tracking-tight text-[#111] mb-4" style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}>
            Interactive Cognitive Playground
          </h1>
          <p className="text-sm sm:text-base text-black/50 leading-relaxed">
            Test the live neurochemical sampling physics and 7-stage cognitive turn tracer, and preview upcoming in-browser tools.
          </p>
        </div>

        {/* Top-Level Studio Navigation */}
        <div className="flex flex-wrap gap-2 mb-8 border-b border-black/[0.08] pb-4">
          {[
            { id: "endocrine", label: "1. Endocrine & LLM Physics", tag: "Live" },
            { id: "turn", label: "2. 7-Stage Cognitive Turn", tag: "Live" },
            { id: "persona", label: "3. Persona Studio & Compiler", tag: "Coming Soon" },
            { id: "voice", label: "4. Acoustic & Prosody Lab", tag: "Coming Soon" },
            { id: "webgpu", label: "5. WebGPU In-Browser Voice", tag: "Coming Soon" },
            { id: "memory_graph", label: "6. 3D Memory & Lexicon Graph", tag: "Coming Soon" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-2.5 rounded-xl text-xs transition-all flex items-center gap-2 ${
                activeTab === tab.id
                  ? "bg-[#111] text-white shadow-xs font-medium"
                  : "bg-white text-black/60 border border-black/[0.06] hover:bg-[#fafaf8]"
              }`}
            >
              <span>{tab.label}</span>
              <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                activeTab === tab.id
                  ? "bg-white/20 text-white"
                  : tab.tag === "Live"
                    ? "bg-emerald-100 text-emerald-800 font-semibold"
                    : "bg-amber-100 text-amber-800 font-semibold"
              }`}>
                {tab.tag}
              </span>
            </button>
          ))}
        </div>

        {/* Tab Content Display */}
        <div className="space-y-8">
          {/* Active Live Tabs */}
          {activeTab === "endocrine" && <EndocrineSimulator />}
          {activeTab === "turn" && <CognitiveTurnFlow />}

          {/* Coming Soon Tabs with Glossy Frosted Blur */}
          {activeTab === "persona" && (
            <ComingSoonOverlay
              title="COMING SOON"
              description="The interactive in-browser Persona Compiler and live dry-run simulator is currently in active development for Phase 8. Full UI layout is previewed below."
              eta="Roadmap v7.1"
              blurAmount="md"
            >
              <PersonaCompilerDemo />
            </ComingSoonOverlay>
          )}

          {activeTab === "voice" && (
            <ComingSoonOverlay
              title="COMING SOON"
              description="The 32kHz neural voice player and emotional prosody testing lab is in active development. Audio sandbox layout previewed below."
              eta="Roadmap v7.1"
              blurAmount="md"
            >
              <VoiceShowcase />
            </ComingSoonOverlay>
          )}

          {activeTab === "webgpu" && (
            <ComingSoonOverlay
              title="COMING SOON"
              description="Zero-install in-browser WebGPU inference for Llama 3.2 1B and GPT-SoVITS voice synthesis is currently in active development for Phase 8."
              eta="Roadmap v7.2"
              blurAmount="md"
            >
              <div className="rounded-2xl border border-black/[0.08] bg-white p-8 space-y-6">
                <div className="flex justify-between items-center border-b border-black/[0.06] pb-4">
                  <div>
                    <h3 className="text-2xl font-light">Client-Side WebGPU Neural Execution</h3>
                    <p className="text-xs text-black/50 mt-1">Run complete 9-agent signal mesh inside WebAssembly + WebGPU</p>
                  </div>
                  <span className="font-mono text-xs px-3 py-1 rounded bg-black/[0.05]">WASM + WGPU</span>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-4 bg-[#fafaf8] rounded-xl border border-black/[0.05]">
                    <span className="text-xs font-mono text-black/40 block mb-1">Local VRAM Allocated</span>
                    <span className="text-2xl font-light font-mono">1.82 GB</span>
                  </div>
                  <div className="p-4 bg-[#fafaf8] rounded-xl border border-black/[0.05]">
                    <span className="text-xs font-mono text-black/40 block mb-1">Inference Engine</span>
                    <span className="text-2xl font-light font-mono">MLC-LLM / WebLLM</span>
                  </div>
                  <div className="p-4 bg-[#fafaf8] rounded-xl border border-black/[0.05]">
                    <span className="text-xs font-mono text-black/40 block mb-1">Audio Synthesis</span>
                    <span className="text-2xl font-light font-mono">ONNX Web Audio</span>
                  </div>
                </div>
                <div className="h-48 bg-[#fafaf8] rounded-xl border border-black/[0.06] flex items-center justify-center font-mono text-xs text-black/30">
                  [ Live WebGPU Canvas Render Target ]
                </div>
              </div>
            </ComingSoonOverlay>
          )}

          {activeTab === "memory_graph" && (
            <ComingSoonOverlay
              title="COMING SOON"
              description="Interactive 3D Three.js force-directed knowledge graph visualizer and learned mental lexicon explorer."
              eta="Roadmap v7.1"
              blurAmount="md"
            >
              <div className="rounded-2xl border border-black/[0.08] bg-white p-8 space-y-6">
                <div className="flex justify-between items-center border-b border-black/[0.06] pb-4">
                  <div>
                    <h3 className="text-2xl font-light">3D Knowledge Graph & Lexicon Topology</h3>
                    <p className="text-xs text-black/50 mt-1">Interactive force-directed graph of Neo4j entities and spreading activation</p>
                  </div>
                  <span className="font-mono text-xs px-3 py-1 rounded bg-black/[0.05]">Three.js WebGL</span>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-4 bg-[#fafaf8] rounded-xl border border-black/[0.05]">
                    <span className="text-xs font-mono text-black/40 block mb-1">Active Memory Nodes</span>
                    <span className="text-2xl font-light font-mono">1,482</span>
                  </div>
                  <div className="p-4 bg-[#fafaf8] rounded-xl border border-black/[0.05]">
                    <span className="text-xs font-mono text-black/40 block mb-1">Lexicon Associative Edges</span>
                    <span className="text-2xl font-light font-mono">4,910</span>
                  </div>
                  <div className="p-4 bg-[#fafaf8] rounded-xl border border-black/[0.05]">
                    <span className="text-xs font-mono text-black/40 block mb-1">ACT-R Decay Constant</span>
                    <span className="text-2xl font-light font-mono">d = 0.50</span>
                  </div>
                </div>
                <div className="h-48 bg-[#fafaf8] rounded-xl border border-black/[0.06] flex items-center justify-center font-mono text-xs text-black/30">
                  [ 3D WebGL Force Directed Graph Viewport ]
                </div>
              </div>
            </ComingSoonOverlay>
          )}
        </div>
      </main>

      <SiteFooter />
    </div>
  )
}
