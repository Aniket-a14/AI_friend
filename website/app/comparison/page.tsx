"use client"

import React, { useState } from "react"
import { MobileNav } from "@/components/mobile-nav"
import { SiteFooter } from "@/components/site-footer"
import { COMPARISON_DATA } from "@/lib/comparison-data"

const CATEGORIES = ["All", "Privacy", "Psychology", "Architecture", "Extensibility"] as const

export default function ComparisonPage() {
  const [selectedCategory, setSelectedCategory] = useState<string>("All")

  const filteredRows = COMPARISON_DATA.filter(
    (row) => selectedCategory === "All" || row.category === selectedCategory
  )

  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />

      <main className="max-w-6xl mx-auto px-6 md:px-12 pt-36 pb-24 space-y-12">
        {/* Header */}
        <div className="max-w-3xl">
          <div className="mb-3 inline-flex items-center gap-2 font-mono text-xs text-black/40">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
            Architectural & Ethical Comparison
          </div>
          <h1 className="text-4xl sm:text-5xl font-light tracking-tight text-[#111] mb-4" style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}>
            Why AI Friend vs Cloud Assistants
          </h1>
          <p className="text-base text-black/50 leading-relaxed">
            An objective architectural breakdown comparing local-first cognitive systems against hosted commercial APIs and character chatbots.
          </p>
        </div>

        {/* Category Filters */}
        <div className="flex flex-wrap gap-2 pb-4 border-b border-black/[0.08]">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-4 py-1.5 rounded-xl text-xs transition-all ${
                selectedCategory === cat
                  ? "bg-[#111] text-white shadow-2xs font-medium"
                  : "bg-white text-black/60 border border-black/[0.06] hover:bg-black/[0.04]"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Comparison Table */}
        <div className="overflow-x-auto rounded-2xl border border-black/[0.08] bg-white shadow-sm">
          <table className="w-full text-left text-xs font-sans">
            <thead className="bg-[#fafaf8] border-b border-black/[0.06] text-[10px] font-mono uppercase text-black/40 tracking-wider">
              <tr>
                <th className="p-4 min-w-[180px]">Feature Dimension</th>
                <th className="p-4 min-w-[220px] bg-black/[0.02] border-x border-black/[0.06] text-black/90 font-semibold">
                  AI Friend (Local-First)
                </th>
                <th className="p-4 min-w-[180px]">Character.ai</th>
                <th className="p-4 min-w-[180px]">OpenAI Realtime</th>
                <th className="p-4 min-w-[180px]">Hume AI (EVI)</th>
                <th className="p-4 min-w-[180px]">ElevenLabs Agents</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-black/[0.04] text-black/70">
              {filteredRows.map((row) => (
                <tr key={row.dimension} className="hover:bg-black/[0.01] transition-colors">
                  <td className="p-4 font-medium text-black/90 align-top">
                    {row.dimension}
                    <span className="block text-[9px] font-mono text-black/35 mt-1 uppercase">
                      {row.category}
                    </span>
                  </td>
                  <td className="p-4 bg-emerald-50/25 border-x border-black/[0.06] text-black/90 font-medium align-top leading-relaxed">
                    {row.aiFriend}
                  </td>
                  <td className="p-4 align-top leading-relaxed text-black/55">{row.characterAi}</td>
                  <td className="p-4 align-top leading-relaxed text-black/55">{row.openAiRealtime}</td>
                  <td className="p-4 align-top leading-relaxed text-black/55">{row.humeEvi}</td>
                  <td className="p-4 align-top leading-relaxed text-black/55">{row.elevenLabsAgents}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>

      <SiteFooter />
    </div>
  )
}

