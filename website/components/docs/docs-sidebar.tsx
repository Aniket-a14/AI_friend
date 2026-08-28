"use client"

import React, { useState, useMemo } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { DOCS_NAV } from "@/lib/docs-nav"

export function DocsSidebar() {
  const pathname = usePathname()
  const [searchQuery, setSearchQuery] = useState("")

  const filteredNav = useMemo(() => {
    if (!searchQuery.trim()) return DOCS_NAV
    const q = searchQuery.toLowerCase()
    return DOCS_NAV.map((section) => ({
      ...section,
      pages: section.pages.filter(
        (p) =>
          p.title.toLowerCase().includes(q) ||
          (p.description && p.description.toLowerCase().includes(q)) ||
          p.slug.toLowerCase().includes(q)
      ),
    })).filter((section) => section.pages.length > 0)
  }, [searchQuery])

  return (
    <nav className="space-y-6">
      {/* Search Input */}
      <div className="relative mb-6">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Filter documentation..."
          className="w-full px-3.5 py-2 text-xs rounded-xl border border-black/[0.08] bg-[#fafaf8] text-black/80 placeholder-black/35 focus:outline-none focus:ring-1 focus:ring-black/20 font-sans"
        />
        {searchQuery && (
          <button
            onClick={() => setSearchQuery("")}
            className="absolute right-3 top-2.5 text-xs text-black/40 hover:text-black"
          >
            ✕
          </button>
        )}
      </div>

      {filteredNav.length === 0 ? (
        <div className="text-xs text-black/40 py-4 text-center">
          No matching documentation pages found.
        </div>
      ) : (
        filteredNav.map((section) => (
          <div key={section.title} className="space-y-1.5">
            <div className="font-mono text-[10px] tracking-widest text-black/35 uppercase px-3 py-1">
              {section.title}
            </div>
            <ul className="space-y-0.5">
              {section.pages.map((page) => {
                const href = `/docs/${page.slug}`
                const active = pathname === href
                return (
                  <li key={page.slug}>
                    <Link
                      href={href}
                      className={`block rounded-xl px-3 py-2 text-xs transition-colors ${
                        active
                          ? "bg-black/[0.06] text-black font-medium"
                          : "text-black/55 hover:text-black hover:bg-black/[0.03]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-1 leading-snug">
                        <span className="truncate">{page.title}</span>
                        {page.comingSoon && (
                          <span className="text-[8px] font-mono uppercase tracking-wider px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 shrink-0">
                            SOON
                          </span>
                        )}
                      </div>
                      {page.description && (
                        <div className="text-[10px] text-black/35 mt-0.5 font-light truncate">
                          {page.description}
                        </div>
                      )}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </div>
        ))
      )}
    </nav>
  )
}
