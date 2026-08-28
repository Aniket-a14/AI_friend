import type { Metadata } from "next"
import Link from "next/link"
import { DOCS_NAV } from "@/lib/docs-nav"

export const metadata: Metadata = {
  title: "Docs — AI Friend",
  description: "Installation, quickstart, architecture, privacy, and troubleshooting for AI Friend.",
}

const SECTION_BLURBS: Record<string, string> = {
  "Getting Started": "One-command install and the four commands that get you talking to your friend.",
  "Concepts": "The mesh architecture, the persona tier boundary, the endocrine layer, and what stays on your machine.",
  "Guides": "Heavier tasks — like fine-tuning a real voice clone — that need a GPU this project doesn't assume you have.",
  "Troubleshooting": "Real gotchas from real runs, not a generic FAQ.",
}

export default function DocsHomePage() {
  return (
    <div>
      <div className="mb-3 inline-flex items-center gap-2 font-mono text-xs text-black/40">
        <span className="h-1.5 w-1.5 rounded-full bg-black/40" />
        Documentation
      </div>
      <h1 className="mb-4 text-4xl md:text-5xl font-light tracking-tight leading-[1.1]" style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}>
        AI Friend Docs
      </h1>
      <p className="mb-12 max-w-xl text-base text-black/50 leading-relaxed">
        Everything here lives in this repo and is checked against the actual
        code, not a separate docs project that can drift from it.
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        {DOCS_NAV.map((section) => (
          <Link
            key={section.title}
            href={`/docs/${section.pages[0].slug}`}
            className="group block rounded-2xl border border-black/[0.07] bg-white p-6 transition-colors hover:border-black/[0.15] hover:bg-[#fafaf8]"
          >
            <h2 className="text-lg font-light mb-2 group-hover:text-black">{section.title}</h2>
            <p className="text-sm text-black/45 leading-relaxed mb-4">{SECTION_BLURBS[section.title]}</p>
            <ul className="space-y-1">
              {section.pages.map((p) => (
                <li key={p.slug} className="text-xs text-black/35">{p.title}</li>
              ))}
            </ul>
          </Link>
        ))}
      </div>
    </div>
  )
}
