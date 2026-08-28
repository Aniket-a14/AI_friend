import type { Metadata } from "next"
import Link from "next/link"
import { MobileNav } from "@/components/mobile-nav"
import { SiteFooter } from "@/components/site-footer"
import { REPO_URL } from "@/lib/site"

export const metadata: Metadata = {
  title: "About — AI Friend",
  description: "About AI Friend: an open-source, local-first AI companion, its license, governance, and how to contribute.",
}

function GitHubLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1.5 text-sm text-black underline underline-offset-4 decoration-black/30 hover:decoration-black transition-colors"
    >
      {children}
      <span aria-hidden="true">↗</span>
    </a>
  )
}

export default function AboutPage() {
  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />

      <section className="max-w-2xl mx-auto px-6 md:px-12 pt-40 pb-24">
        <div className="mb-3 inline-flex items-center gap-2 font-mono text-xs text-black/40">
          <span className="h-1.5 w-1.5 rounded-full bg-black/40" />
          About
        </div>
        <h1 className="text-4xl sm:text-5xl font-light tracking-tight mb-6" style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}>
          Built in the open.
        </h1>
        <p className="text-base text-black/50 leading-relaxed">
          AI Friend is a local-first AI companion you describe in your own
          words — a persona compiler, an endocrine layer that measurably
          modulates how the model generates, a memory system that learns
          its own associations, and a cloned voice, all running on your own
          hardware. It's built as an open project: the code, the reasoning
          behind it, and the way it's governed are all public — including
          what was tried and didn't work, in
          {" "}<Link href="/docs" className="text-black underline underline-offset-4 decoration-black/30 hover:decoration-black">the docs</Link>.
        </p>

        <div className="mt-16 border-t border-black/[0.06] pt-10">
          <h2 className="text-xl font-light mb-3">Open source</h2>
          <p className="text-sm text-black/50 leading-relaxed mb-3">
            AI Friend is released under the <strong className="text-black/80 font-medium">MIT license</strong> —
            a permissive license. You can use it, modify it, and ship it in
            a commercial product without asking permission or paying
            anything; the only real condition is keeping the copyright
            notice intact. Like almost all open-source licenses, it comes
            with no warranty.
          </p>
          <GitHubLink href={`${REPO_URL}/blob/main/LICENSE`}>Read the full license on GitHub</GitHubLink>
        </div>

        <div className="mt-12 border-t border-black/[0.06] pt-10">
          <h2 className="text-xl font-light mb-3">Contributing</h2>
          <p className="text-sm text-black/50 leading-relaxed mb-3">
            Contributions go through a branch and a pull request against
            `main`. New tests are expected to be mutation-tested — break the
            code they cover and confirm they fail — and the full backend
            suite plus `ruff check .` need to be green before it's done.
            `.agents/CONTEXT.md`, the engineering ledger, records what was
            actually built and measured; it's worth reading before a
            non-trivial change.
          </p>
          <GitHubLink href={`${REPO_URL}/blob/main/CONTRIBUTING.md`}>Read the contributing guide on GitHub</GitHubLink>
        </div>

        <div className="mt-12 border-t border-black/[0.06] pt-10">
          <h2 className="text-xl font-light mb-3">Governance</h2>
          <p className="text-sm text-black/50 leading-relaxed mb-3">
            This is currently a single-maintainer project. Day-to-day
            decisions go through PR review; architectural decisions —
            anything touching the cognitive core, the affect model, or the
            persona boundary — are made by the lead maintainer, with the
            reasoning recorded rather than left implicit.
          </p>
          <GitHubLink href={`${REPO_URL}/blob/main/GOVERNANCE.md`}>Read the governance doc on GitHub</GitHubLink>
        </div>

        <div className="mt-12 border-t border-black/[0.06] pt-10">
          <h2 className="text-xl font-light mb-3">Security</h2>
          <p className="text-sm text-black/50 leading-relaxed mb-3">
            No conversation leaves your hardware by default, and nothing
            here collects telemetry. If you find a vulnerability, the ask
            is simple: don't open a public issue. Report it privately first,
            so there's a fix out before the details are.
          </p>
          <GitHubLink href={`${REPO_URL}/blob/main/SECURITY.md`}>Read the full security policy on GitHub</GitHubLink>
        </div>

        <div className="mt-12 border-t border-black/[0.06] pt-10">
          <h2 className="text-xl font-light mb-3">Community standards</h2>
          <p className="text-sm text-black/50 leading-relaxed mb-3">
            The short version: be someone people want to collaborate with.
            Disagreements about code and design are normal and welcome;
            personal attacks and bad-faith arguments aren't. The full
            policy is adapted from the Contributor Covenant, and it's the
            same standard for everyone — maintainers included.
          </p>
          <GitHubLink href={`${REPO_URL}/blob/main/CODE_OF_CONDUCT.md`}>Read the code of conduct on GitHub</GitHubLink>
        </div>

        <div className="mt-16 flex flex-wrap gap-3 border-t border-black/[0.06] pt-10">
          <Link
            href="/docs"
            className="inline-flex items-center gap-2 rounded-full bg-[#111] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#333]"
          >
            Read the docs
          </Link>
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-full border border-black/10 px-5 py-2.5 text-sm font-medium text-black transition-colors hover:bg-black/[0.04]"
          >
            View the repository
          </a>
        </div>
      </section>

      <SiteFooter />
    </div>
  )
}
