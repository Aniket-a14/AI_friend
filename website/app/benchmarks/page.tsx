"use client"

import React, { useState } from "react"
import { MobileNav } from "@/components/mobile-nav"
import { SiteFooter } from "@/components/site-footer"
import {
  PRESSURE_SCENARIOS,
  HARDWARE_MATRIX,
  LATENCY_WATERFALL,
  CONTAINER_FOOTPRINTS,
  REAL_MICRO_BENCHMARKS,
} from "@/lib/benchmark-data"

export default function BenchmarksPage() {
  const [selectedScenarioId, setSelectedScenarioId] = useState<number>(1)

  const activeScenario = PRESSURE_SCENARIOS.find((s) => s.id === selectedScenarioId) || PRESSURE_SCENARIOS[0]

  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />

      <main className="max-w-6xl mx-auto px-6 md:px-12 pt-36 pb-24 space-y-16">
        {/* Header */}
        <div className="max-w-3xl">
          <div className="mb-3 inline-flex items-center gap-2 font-mono text-xs text-black/40">
            <span className="h-1.5 w-1.5 rounded-full bg-purple-500" />
            Verified Empirical Measurements (tools/measure/out/)
          </div>
          <h1 className="text-4xl sm:text-5xl font-light tracking-tight text-[#111] mb-4" style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}>
            Empirical Hardware Benchmarks
          </h1>
          <p className="text-base text-black/50 leading-relaxed">
            Real forensic measurements executed against physical hardware (17.18 GB Unified Memory Host) across 9 simultaneous multimodal pressure scenarios and micro-benchmark test harnesses.
          </p>
        </div>

        {/* Section 1: The 9 Multimodal Pressure Scenarios */}
        <section className="space-y-6">
          <div className="border-b border-black/[0.08] pb-4 flex flex-col sm:flex-row sm:items-end justify-between gap-2">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-black/40">AUDIT.md §17 Scenarios</span>
              <h2 className="text-2xl font-light text-[#111] mt-1">The 9 Multimodal Pressure Scenarios</h2>
              <p className="text-xs text-black/50 mt-1">
                Select a scenario to inspect measured RAM consumption and active concurrency contention.
              </p>
            </div>
            <span className="font-mono text-[10px] text-emerald-800 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200 self-start sm:self-auto">
              ✓ Verified Live Data
            </span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Scenario List */}
            <div className="lg:col-span-5 space-y-2">
              {PRESSURE_SCENARIOS.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setSelectedScenarioId(s.id)}
                  className={`w-full text-left p-3.5 rounded-xl border transition-all flex items-center justify-between ${
                    selectedScenarioId === s.id
                      ? "bg-[#111] text-white border-[#111] shadow-xs"
                      : "bg-white text-black/70 border-black/[0.06] hover:bg-[#fafaf8]"
                  }`}
                >
                  <div className="min-w-0 pr-2">
                    <span className={`font-mono text-[10px] block ${selectedScenarioId === s.id ? "text-white/50" : "text-black/35"}`}>
                      Scenario {s.id.toString().padStart(2, "0")}
                    </span>
                    <span className="text-xs font-medium truncate block mt-0.5">{s.name}</span>
                  </div>
                  <span className="font-mono text-xs font-semibold shrink-0">
                    {s.ramUsedGB.toFixed(2)} GB
                  </span>
                </button>
              ))}
            </div>

            {/* Scenario Detail Card */}
            <div className="lg:col-span-7 rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 flex flex-col justify-between shadow-xs">
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-black/[0.06] pb-4">
                  <div>
                    <span className="text-[10px] font-mono uppercase text-black/35">Scenario {activeScenario.id.toString().padStart(2, "0")}</span>
                    <h3 className="text-xl font-light text-[#111] mt-0.5">{activeScenario.name}</h3>
                  </div>
                  <div className="text-right">
                    <span className="text-2xl font-light font-mono text-[#111]">{activeScenario.ramUsedGB.toFixed(2)} <span className="text-xs text-black/40">GB</span></span>
                    <span className="text-[10px] text-black/40 block">
                      {activeScenario.deltaFromIdleGB >= 0 ? `+${activeScenario.deltaFromIdleGB.toFixed(2)} GB` : `${activeScenario.deltaFromIdleGB.toFixed(2)} GB`} from idle
                    </span>
                  </div>
                </div>

                <p className="text-sm text-black/60 leading-relaxed">{activeScenario.description}</p>

                <div>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-black/35 block mb-2">Active Mesh Components</span>
                  <div className="flex flex-wrap gap-1.5">
                    {activeScenario.activeComponents.map((c) => (
                      <span key={c} className="px-2.5 py-1 rounded bg-[#fafaf8] border border-black/[0.06] text-[11px] font-mono text-black/70">
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-black/[0.06] space-y-2">
                <div className="bg-[#fafaf8] rounded-xl p-4 border border-black/[0.04] text-xs text-black/60">
                  <span className="font-semibold text-black/80 block mb-1">Key Empirical Finding:</span>
                  {activeScenario.notes}
                </div>
                <span className="font-mono text-[10px] text-black/35 block">
                  Provenance: {activeScenario.measuredProvenance}
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Section 2: Real Micro-Benchmarks (tools/measure/out/) */}
        <section className="space-y-6">
          <div className="border-b border-black/[0.08] pb-4">
            <span className="text-[10px] font-mono uppercase tracking-widest text-black/40">Subsystem Measurements</span>
            <h2 className="text-2xl font-light text-[#111] mt-1">Subsystem Micro-Benchmarks</h2>
            <p className="text-xs text-black/50 mt-1">
              Exact timings captured from test suites and live measurement runs in tools/measure/out/.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {REAL_MICRO_BENCHMARKS.map((m) => (
              <div key={m.measurementId} className="rounded-xl border border-black/[0.06] bg-white p-5 flex flex-col justify-between shadow-2xs">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-[10px] text-black/40 uppercase bg-black/[0.03] px-2 py-0.5 rounded">
                      {m.measurementId}
                    </span>
                    <span className="text-[10px] font-mono text-emerald-700 font-medium">● LIVE</span>
                  </div>
                  <h3 className="text-base font-medium text-black/90 mb-1">{m.title}</h3>
                  <div className="text-2xl font-light font-mono text-black/95 my-2">
                    {m.measuredValue}
                  </div>
                  <p className="text-xs text-black/50 leading-relaxed">{m.conditions}</p>
                </div>
                <div className="mt-4 pt-2 border-t border-black/[0.04] text-[10px] font-mono text-black/40">
                  Unit: {m.benchmarkUnit}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Section 3: Docker Container Infrastructure Memory Breakdown */}
        <section className="space-y-6">
          <div className="border-b border-black/[0.08] pb-4">
            <span className="text-[10px] font-mono uppercase tracking-widest text-black/40">Infrastructure Footprint</span>
            <h2 className="text-2xl font-light text-[#111] mt-1">Docker Mesh Memory Breakdown (752.4 MiB Total)</h2>
            <p className="text-xs text-black/50 mt-1">
              Measured resident container memory across the 6 core backend services.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {CONTAINER_FOOTPRINTS.map((c) => (
              <div key={c.service} className="p-4 rounded-xl border border-black/[0.06] bg-white text-center space-y-1">
                <span className="font-mono text-xl font-light text-black/90 block">{c.memoryMiB} <span className="text-[10px] text-black/40 font-sans">MiB</span></span>
                <span className="text-xs font-medium text-black/80 block">{c.service}</span>
                <span className="text-[10px] text-black/40 font-mono block">Port {c.port}</span>
              </div>
            ))}
          </div>
        </section>

        {/* Section 4: Hardware Platform Matrix */}
        <section className="space-y-6">
          <div className="border-b border-black/[0.08] pb-4">
            <span className="text-[10px] font-mono uppercase tracking-widest text-black/40">Compatibility & Profiles</span>
            <h2 className="text-2xl font-light text-[#111] mt-1">Platform Performance Matrix</h2>
            <p className="text-xs text-black/50 mt-1">
              Engineering targets the architecture is designed for, not live measurements — see Section 2 above for what's actually been measured.
            </p>
          </div>

          <div className="overflow-x-auto rounded-2xl border border-black/[0.08] bg-white shadow-xs">
            <table className="w-full text-left text-xs font-sans">
              <thead className="bg-[#fafaf8] border-b border-black/[0.06] text-[10px] font-mono uppercase text-black/40 tracking-wider">
                <tr>
                  <th className="p-4">Hardware Target</th>
                  <th className="p-4">Launch Profile</th>
                  <th className="p-4">LLM Inference Engine</th>
                  <th className="p-4">Voice Engine</th>
                  <th className="p-4">Time-To-First-Token</th>
                  <th className="p-4">Total Turnaround</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-black/[0.04] text-black/70">
                {HARDWARE_MATRIX.map((row) => (
                  <tr key={row.platform} className="hover:bg-[#fafaf8] transition-colors">
                    <td className="p-4 font-medium text-black/90">{row.platform}</td>
                    <td className="p-4">{row.profile}</td>
                    <td className="p-4 font-mono text-black/60">{row.llmInference}</td>
                    <td className="p-4 font-mono text-black/60">{row.voiceEngine}</td>
                    <td className="p-4 font-mono text-blue-700/80 font-semibold">{row.ttftMs}</td>
                    <td className="p-4 font-mono font-semibold text-black/90">{row.totalTurnaroundMs}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Section 5: Latency Waterfall Breakdown */}
        <section className="space-y-6">
          <div className="border-b border-black/[0.08] pb-4">
            <span className="text-[10px] font-mono uppercase tracking-widest text-black/40">Step-by-Step Breakdown</span>
            <h2 className="text-2xl font-light text-[#111] mt-1">Conversational Loop Latency Waterfall</h2>
            <p className="text-xs text-black/50 mt-1">
              A per-stage budget, not a measured trace — the direct attempt to measure this loop (m14_stt_cost.json) came back UNKNOWN because stt-agent wasn't running for that run.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {LATENCY_WATERFALL.map((item, idx) => (
              <div key={item.step} className="rounded-xl border border-black/[0.06] bg-white p-5 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-[10px] text-black/35">Step 0{idx + 1}</span>
                    <span className="font-mono text-sm font-semibold text-black/90">{item.latencyMs} ms</span>
                  </div>
                  <h4 className="text-sm font-medium text-black/80 mb-1">{item.step}</h4>
                  <p className="text-xs text-black/45 leading-relaxed">{item.detail}</p>
                </div>
                <div className="mt-4 pt-2 border-t border-black/[0.04] text-[10px] font-mono text-black/40">
                  {item.agent}
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  )
}
