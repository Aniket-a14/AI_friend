"use client"

import React, { useState, useMemo } from "react"
import { MobileNav } from "@/components/mobile-nav"
import { SiteFooter } from "@/components/site-footer"
import { CHANGELOG_DATA } from "@/lib/changelog-data"
import { ComingSoonOverlay } from "@/components/coming-soon-overlay"

const ALL_TAGS = ["All", "Core", "Voice", "Memory", "UI", "Security", "Benchmarks", "Infrastructure"] as const

export default function ChangelogPage() {
  const [selectedTag, setSelectedTag] = useState<string>("All")
  const [searchQuery, setSearchQuery] = useState("")

  const filteredReleases = useMemo(() => {
    return CHANGELOG_DATA.filter((item) => {
      const matchesTag = selectedTag === "All" || item.tags.includes(selectedTag as any)
      const q = searchQuery.toLowerCase()
      const matchesSearch =
        !q ||
        item.title.toLowerCase().includes(q) ||
        item.summary.toLowerCase().includes(q) ||
        item.version.toLowerCase().includes(q) ||
        item.highlights.some((h) => h.toLowerCase().includes(q))
      return matchesTag && matchesSearch
    })
  }, [selectedTag, searchQuery])

  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />

      <main className="max-w-4xl mx-auto px-6 md:px-12 pt-36 pb-24">
        {/* Header */}
        <div className="mb-10">
          <div className="mb-3 inline-flex items-center gap-2 font-mono text-xs text-black/40">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
            Engineering Release Ledger
          </div>
          <h1 className="text-4xl sm:text-5xl font-light tracking-tight text-[#111] mb-4" style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}>
            Changelog & Roadmap History
          </h1>
          <p className="text-base text-black/50 leading-relaxed max-w-2xl">
            A chronological, verified record of all major architectural phases, performance baselines, and upcoming roadmap releases.
          </p>
        </div>

        {/* Filters and Search Bar */}
        <div className="flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center mb-10 pb-6 border-b border-black/[0.08]">
          <div className="flex flex-wrap gap-1.5">
            {ALL_TAGS.map((tag) => (
              <button
                key={tag}
                onClick={() => setSelectedTag(tag)}
                className={`px-3 py-1 rounded-full text-xs transition-all ${
                  selectedTag === tag
                    ? "bg-[#111] text-white shadow-2xs font-medium"
                    : "bg-white text-black/60 border border-black/[0.06] hover:bg-black/[0.04]"
                }`}
              >
                {tag}
              </button>
            ))}
          </div>

          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search releases..."
            className="px-3.5 py-1.5 rounded-xl border border-black/[0.08] bg-white text-xs text-black/80 placeholder-black/35 focus:outline-none focus:ring-1 focus:ring-black/20 w-full sm:w-56"
          />
        </div>

        {/* Release Timeline */}
        <div className="space-y-12">
          {filteredReleases.map((release) => {
            const articleContent = (
              <article
                className={`relative pl-6 sm:pl-8 border-l border-black/[0.1] space-y-4 ${
                  release.status === "Coming Soon" ? "opacity-90" : ""
                }`}
              >
                {/* Timeline marker */}
                <span className={`absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full ${
                  release.status === "Coming Soon" ? "bg-amber-400 animate-pulse" : "bg-[#111]"
                } ring-4 ring-[#F5F4F0]`} />

                <div className="flex flex-wrap items-center gap-3">
                  <span className={`font-mono text-xs font-semibold px-2.5 py-0.5 rounded ${
                    release.status === "Coming Soon" ? "bg-amber-500 text-white" : "bg-[#111] text-white"
                  }`}>
                    {release.version}
                  </span>
                  <span className="text-xs text-black/40 font-mono">{release.date}</span>
                  {release.status === "Coming Soon" && (
                    <span className="font-mono text-[9px] uppercase tracking-widest px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 border border-amber-300 font-semibold">
                      ROADMAP TARGET
                    </span>
                  )}
                  <div className="flex gap-1.5 ml-auto">
                    {release.tags.map((t) => (
                      <span key={t} className="text-[10px] font-mono px-2 py-0.5 rounded bg-black/[0.04] text-black/55">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>

                <h2 className="text-2xl font-light text-[#111]">{release.title}</h2>
                <p className="text-sm text-black/60 leading-relaxed">{release.summary}</p>

                {/* Highlights */}
                <div className="bg-white rounded-xl border border-black/[0.06] p-5 space-y-2">
                  <span className="text-[10px] font-mono uppercase tracking-widest text-black/35 block mb-2">Key Highlights</span>
                  <ul className="space-y-1.5 list-disc pl-4 text-xs text-black/70 leading-relaxed">
                    {release.highlights.map((h, i) => (
                      <li key={i}>{h}</li>
                    ))}
                  </ul>
                </div>

                {/* Metrics if available */}
                {release.metrics && (
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2">
                    {release.metrics.map((m) => (
                      <div key={m.label} className="p-3 bg-[#fafaf8] rounded-lg border border-black/[0.05]">
                        <span className="text-[10px] font-mono uppercase text-black/35 block">{m.label}</span>
                        <span className="text-sm font-mono font-medium text-black/90 mt-0.5 block">{m.value}</span>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            )

            if (release.status === "Coming Soon") {
              return (
                <ComingSoonOverlay
                  key={release.version}
                  title="COMING SOON"
                  description="Upcoming architectural milestone scheduled in the community roadmap."
                  eta={release.date}
                  blurAmount="sm"
                >
                  {articleContent}
                </ComingSoonOverlay>
              )
            }

            return <div key={release.version}>{articleContent}</div>
          })}
        </div>
      </main>

      <SiteFooter />
    </div>
  )
}
