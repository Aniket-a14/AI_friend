import type { ReactNode } from "react"
import { MobileNav } from "@/components/mobile-nav"
import { DocsSidebar } from "@/components/docs/docs-sidebar"

export default function DocsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />
      <div className="h-24" />
      <div className="mx-auto flex w-full max-w-6xl items-start gap-12 px-6 md:px-12">
        <aside className="hidden w-56 shrink-0 lg:sticky lg:top-24 lg:block lg:h-[calc(100vh-7rem)] lg:overflow-y-auto lg:pb-12">
          <DocsSidebar />
        </aside>
        <div className="min-w-0 flex-1 pb-24 lg:h-[calc(100vh-7rem)] lg:overflow-y-auto lg:pr-2">{children}</div>
      </div>
    </div>
  )
}
