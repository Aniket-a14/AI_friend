"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { DOCS_NAV } from "@/lib/docs-nav"

export function DocsSidebar() {
  const pathname = usePathname()

  return (
    <nav className="space-y-8">
      {DOCS_NAV.map((section) => (
        <div key={section.title}>
          <div className="font-pixel text-[10px] tracking-widest text-black/30 uppercase mb-2">
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
                    className={`block rounded-lg px-3 py-1.5 text-sm transition-colors ${
                      active
                        ? "bg-black/[0.06] text-black font-medium"
                        : "text-black/50 hover:text-black hover:bg-black/[0.03]"
                    }`}
                  >
                    {page.title}
                  </Link>
                </li>
              )
            })}
          </ul>
        </div>
      ))}
    </nav>
  )
}
