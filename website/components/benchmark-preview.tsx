"use client"

import React from "react"
import Link from "next/link"
import { HARDWARE_MATRIX, LATENCY_WATERFALL } from "@/lib/benchmark-data"

export function BenchmarkPreview() {
  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 pb-6 border-b border-black/[0.06]">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 bg-black/[0.04] px-2.5 py-1 rounded-full">
            Empirical Hardware Measurements
          </span>
          <h3 className="text-2xl font-light tracking-tight mt-2 text-[#111]">
            Hardware Matrix & Latency Waterfalls
          </h3>
          <p className="text-xs text-black/45 mt-1">
            Every figure measured on live physical hardware — no theoretical estimates presented as results.
          </p>
        </div>

        <Link
          href="/benchmarks"
          className="px-4 py-2 rounded-xl bg-[#111] text-white text-xs font-medium hover:bg-[#333] transition-colors self-start md:self-auto"
        >
          Explore All 9 Scenarios →
        </Link>
      </div>

      {/* Hardware Matrix Table */}
      <div className="overflow-x-auto rounded-xl border border-black/[0.06] mb-6">
        <table className="w-full text-left text-xs font-sans">
          <thead className="bg-[#fafaf8] border-b border-black/[0.06] text-[10px] font-mono uppercase text-black/40 tracking-wider">
            <tr>
              <th className="p-3.5">Hardware Platform</th>
              <th className="p-3.5">Operational Profile</th>
              <th className="p-3.5">LLM Time-To-First-Token</th>
              <th className="p-3.5">Total Loop Turnaround</th>
              <th className="p-3.5">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/[0.04] text-black/70">
            {HARDWARE_MATRIX.map((row) => (
              <tr key={row.platform} className="hover:bg-black/[0.01] transition-colors">
                <td className="p-3.5 font-medium text-black/90">{row.platform}</td>
                <td className="p-3.5">{row.profile}</td>
                <td className="p-3.5 font-mono text-blue-700/80">{row.ttftMs}</td>
                <td className="p-3.5 font-mono font-medium text-black/90">{row.totalTurnaroundMs}</td>
                <td className="p-3.5 text-[11px]">
                  <span className="px-2 py-0.5 rounded bg-black/[0.04] text-black/60 font-mono">
                    {row.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Latency Breakdown Bar */}
      <div className="bg-[#fafaf8] rounded-xl border border-black/[0.06] p-5">
        <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 block mb-3">
          Turnaround Latency Composition (Speech → Cognitive Appraisal → 32kHz Audio Output)
        </span>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {LATENCY_WATERFALL.slice(0, 4).map((item) => (
            <div key={item.step} className="bg-white p-3 rounded-lg border border-black/[0.06]">
              <span className="text-xl font-light font-mono text-black/90">{item.latencyMs} <span className="text-[10px] text-black/40">ms</span></span>
              <span className="text-[11px] font-medium text-black/70 block mt-0.5">{item.step}</span>
              <span className="text-[10px] text-black/35 font-mono block mt-0.5">{item.agent}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
