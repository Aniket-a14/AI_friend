"use client"

import { useState } from "react"
import Link from "next/link"

const NAV_LINKS = [
  { label: "Download",    href: "/download" },
  { label: "Playground",  href: "/playground" },
  { label: "Docs",        href: "/docs" },
  { label: "Benchmarks",  href: "/benchmarks" },
  { label: "Changelog",   href: "/changelog" },
  { label: "Comparison",  href: "/comparison" },
  { label: "Research",    href: "/research" },
  { label: "Showcase",    href: "/showcase" },
  { label: "About",       href: "/about" },
]

const NAV_STYLE = {
  backdropFilter: "blur(16px)",
  WebkitBackdropFilter: "blur(16px)",
  background: "rgba(245,244,240,0.65)",
  boxShadow: "0 8px 32px rgba(0,0,0,0.06), 0 2px 8px rgba(0,0,0,0.04)",
} as const

export function MobileNav() {
  const [open, setOpen] = useState(false)

  const close = () => setOpen(false)

  return (
    <div className="fixed top-4 inset-x-0 z-50 flex justify-center px-4 pointer-events-none">
      <div className="pointer-events-auto w-full max-w-5xl">

        {/* Main bar */}
        <nav
          className="flex items-center justify-between px-6 py-3 rounded-2xl border border-black/[0.08]"
          style={NAV_STYLE}
        >
          <Link href="/" className="flex items-center gap-2.5 font-mono text-xs font-semibold tracking-[0.25em] text-[#111] hover:opacity-75 transition-opacity">
            <img src="/icon.svg" alt="AI Friend Logo" className="w-5 h-5 rounded-md" />
            <span>AI FRIEND</span>
          </Link>

          {/* Desktop links */}
          <div className="hidden lg:flex items-center gap-6" style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}>
            {NAV_LINKS.map(l => (
              <Link
                key={l.label}
                href={l.href}
                className="text-[11px] text-black/60 hover:text-black transition-colors duration-200 tracking-wide font-medium"
              >
                {l.label}
              </Link>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/#setup"
              className="text-[11px] px-4 py-2 rounded-xl bg-[#111] text-white hover:bg-[#333] transition-all duration-200 tracking-wider font-medium hidden sm:block"
              style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
            >
              GET STARTED
            </Link>

            {/* Burger — mobile only */}
            <button
              onClick={() => setOpen(v => !v)}
              className="lg:hidden flex flex-col justify-center items-center w-8 h-8 gap-[5px] rounded-lg hover:bg-black/[0.04] transition-colors"
              aria-label={open ? "Close menu" : "Open menu"}
            >
              <span
                className="block h-px bg-black/70 transition-all duration-300 origin-center"
                style={{
                  width: "18px",
                  transform: open ? "translateY(6px) rotate(45deg)" : "none",
                }}
              />
              <span
                className="block h-px bg-black/70 transition-all duration-300"
                style={{
                  width: "18px",
                  opacity: open ? 0 : 1,
                  transform: open ? "scaleX(0)" : "none",
                }}
              />
              <span
                className="block h-px bg-black/70 transition-all duration-300 origin-center"
                style={{
                  width: "18px",
                  transform: open ? "translateY(-6px) rotate(-45deg)" : "none",
                }}
              />
            </button>
          </div>
        </nav>

        {/* Mobile dropdown */}
        <div
          className="lg:hidden mt-2 overflow-hidden transition-all duration-300 ease-in-out"
          style={{ maxHeight: open ? "420px" : "0px", opacity: open ? 1 : 0 }}
        >
          <div
            className="rounded-2xl border border-black/[0.08] px-3 py-3 flex flex-col gap-1"
            style={NAV_STYLE}
          >
            {NAV_LINKS.map(l => (
              <Link
                key={l.label}
                href={l.href}
                onClick={close}
                className="px-4 py-2.5 text-xs text-black/70 hover:text-black hover:bg-black/[0.04] rounded-xl transition-colors tracking-wide font-medium"
                style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
              >
                {l.label}
              </Link>
            ))}
            <div className="mt-2 pt-2 border-t border-black/[0.06]">
              <Link
                href="/#setup"
                onClick={close}
                className="block w-full text-center text-xs px-4 py-2.5 rounded-xl bg-[#111] text-white hover:bg-[#333] transition-all duration-200 tracking-wider font-medium"
                style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
              >
                GET STARTED
              </Link>
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}
