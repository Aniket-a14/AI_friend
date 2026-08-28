import Link from "next/link"
import { REPO_URL } from "@/lib/site"

const SECTION_LINKS = [
  { label: "How it's different", href: "/#how" },
  { label: "The mesh", href: "/#mesh" },
  { label: "Get started", href: "/#setup" },
  { label: "The stack", href: "/#tech" },
  { label: "Privacy", href: "/#privacy" },
]

const PAGE_LINKS = [
  { label: "Docs", href: "/docs" },
  { label: "About", href: "/about" },
  { label: "License", href: `${REPO_URL}/blob/main/LICENSE`, external: true },
  { label: "GitHub", href: REPO_URL, external: true },
]

export function SiteFooter() {
  return (
    <footer className="py-10 px-6 md:px-12 lg:px-20 border-t border-black/[0.06]">
      <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-8">
        <span className="font-pixel text-xs tracking-[0.25em] text-black/50">AI FRIEND</span>

        <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
          {SECTION_LINKS.map((l) => (
            <a key={l.label} href={l.href} className="text-xs text-black/35 hover:text-black/70 transition-colors tracking-widest">
              {l.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-6">
          {PAGE_LINKS.map((l) =>
            l.external ? (
              <a key={l.label} href={l.href} target="_blank" rel="noopener noreferrer" className="text-xs text-black/25 hover:text-black/55 transition-colors tracking-widest">
                {l.label}
              </a>
            ) : (
              <Link key={l.label} href={l.href} className="text-xs text-black/25 hover:text-black/55 transition-colors tracking-widest">
                {l.label}
              </Link>
            ),
          )}
        </div>
      </div>
      <div className="max-w-6xl mx-auto mt-8 pt-6 border-t border-black/[0.04]">
        <span className="text-xs text-black/20">MIT licensed. An open-source, self-hosted project — no service operated on your behalf.</span>
      </div>
    </footer>
  )
}
