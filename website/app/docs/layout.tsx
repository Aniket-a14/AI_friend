import type { ReactNode } from "react"
import { MobileNav } from "@/components/mobile-nav"
import { DocsSidebar } from "@/components/docs/docs-sidebar"
import { SiteFooter } from "@/components/site-footer"

export default function DocsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />
      <div className="h-24" />
      <div className="mx-auto flex w-full max-w-6xl items-start gap-12 px-6 md:px-12 pb-24">
        <aside className="sticky top-24 hidden w-56 shrink-0 lg:block">
          <DocsSidebar />
        </aside>
        <div className="min-w-0 flex-1">{children}</div>
      </div>
      <SiteFooter />
    </div>
  )
}
