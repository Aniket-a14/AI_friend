"use client"

import React from "react"
import Link from "next/link"
import { MobileNav } from "@/components/mobile-nav"
import { SiteFooter } from "@/components/site-footer"
import { OSInstallTabs } from "@/components/os-install-tabs"
import { REPO_URL } from "@/lib/site"

export default function DownloadPage() {
  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />

      <main className="max-w-6xl mx-auto px-6 md:px-12 pt-36 pb-24 space-y-16">
        {/* Header */}
        <div className="max-w-3xl">
          <div className="mb-3 inline-flex items-center gap-2 font-mono text-xs text-black/40">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Cross-Platform Download & Install Center
          </div>
          <h1 className="text-4xl sm:text-5xl font-light tracking-tight text-[#111] mb-4" style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}>
            Get AI Friend for Your Platform
          </h1>
          <p className="text-base text-black/50 leading-relaxed">
            You don't need to clone the full repository to run your friend. Download the <strong>compact 4.3 MB standalone runtime bundle</strong> or run the 1-line automated installer. Fully model-agnostic, MIT licensed, and 100% local.
          </p>
        </div>

        {/* Section 1: Automated 1-Liner Install Tabs */}
        <section className="space-y-4">
          <div className="flex items-center justify-between border-b border-black/[0.08] pb-3">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-black/40">Method 1 (Recommended)</span>
              <h2 className="text-2xl font-light text-[#111] mt-0.5">Automated One-Line Installer</h2>
              <p className="text-xs text-black/50 mt-0.5">Downloads the lightweight runtime and installs the global 'friend' CLI.</p>
            </div>
          </div>

          <OSInstallTabs />
        </section>

        {/* Section 2: Standalone Runtime Packages (< 5 MB) vs Developer Monorepo */}
        <section className="space-y-6">
          <div className="border-b border-black/[0.08] pb-3 flex flex-col sm:flex-row sm:items-end justify-between gap-2">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-black/40">Method 2</span>
              <h2 className="text-2xl font-light text-[#111] mt-0.5">Standalone Runtime Packages (4.3 MB)</h2>
              <p className="text-xs text-black/50 mt-1">
                Zero website source, zero benchmark logs — contains only runtime orchestration, CLI wizards, and config templates.
              </p>
            </div>
            <span className="text-[11px] font-mono text-black/40 bg-black/[0.04] px-2.5 py-1 rounded-full self-start sm:self-auto">
              Compact Size: ~4.3 MB
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Runtime tar.gz */}
            <div className="bg-white rounded-2xl border border-black/[0.08] p-6 flex flex-col justify-between shadow-2xs space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold text-black/80">macOS & Linux</span>
                  <span className="text-[10px] font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">4.3 MB</span>
                </div>
                <h3 className="text-lg font-light">Standalone Runtime Archive</h3>
                <p className="text-xs text-black/55 leading-relaxed">
                  Includes <code className="font-mono bg-black/[0.04] px-1">start.sh</code>, <code className="font-mono bg-black/[0.04] px-1">friend</code> CLI, compose files, and voice provisioners.
                </p>
              </div>
              <div className="space-y-2 pt-4 border-t border-black/[0.06]">
                <a
                  href={`${REPO_URL}/raw/main/dist/ai-friend-runtime.tar.gz`}
                  className="w-full py-2.5 rounded-xl bg-[#111] text-white text-xs font-medium hover:bg-[#333] transition-colors flex items-center justify-center gap-2"
                >
                  <span>Download .tar.gz (4.3 MB)</span>
                  <span>↓</span>
                </a>
                <span className="text-[10px] font-mono text-black/40 block text-center">SHA-256 Verified · MIT License</span>
              </div>
            </div>

            {/* Windows zip */}
            <div className="bg-white rounded-2xl border border-black/[0.08] p-6 flex flex-col justify-between shadow-2xs space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold text-black/80">Windows 10/11</span>
                  <span className="text-[10px] font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">4.4 MB</span>
                </div>
                <h3 className="text-lg font-light">Windows Standalone Zip</h3>
                <p className="text-xs text-black/55 leading-relaxed">
                  Includes <code className="font-mono bg-black/[0.04] px-1">start.bat</code> double-click launcher, <code className="font-mono bg-black/[0.04] px-1">start.ps1</code>, and compose files.
                </p>
              </div>
              <div className="space-y-2 pt-4 border-t border-black/[0.06]">
                <a
                  href={`${REPO_URL}/raw/main/dist/ai-friend-runtime.zip`}
                  className="w-full py-2.5 rounded-xl bg-[#111] text-white text-xs font-medium hover:bg-[#333] transition-colors flex items-center justify-center gap-2"
                >
                  <span>Download .zip (4.4 MB)</span>
                  <span>↓</span>
                </a>
                <span className="text-[10px] font-mono text-black/40 block text-center">SHA-256 Verified · MIT License</span>
              </div>
            </div>

            {/* Developer Full Source */}
            <div className="bg-white rounded-2xl border border-black/[0.08] p-6 flex flex-col justify-between shadow-2xs space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-semibold text-black/80">Developer Monorepo</span>
                  <span className="text-[10px] font-mono text-black/40">Full Repo</span>
                </div>
                <h3 className="text-lg font-light">Full Source & Evals</h3>
                <p className="text-xs text-black/55 leading-relaxed">
                  Complete repository with website, empirical benchmark harnesses, and academic eval probes.
                </p>
              </div>
              <div className="space-y-2 pt-4 border-t border-black/[0.06]">
                <a
                  href={`${REPO_URL}/archive/refs/heads/main.tar.gz`}
                  className="w-full py-2.5 rounded-xl bg-black/[0.05] text-black/80 text-xs font-medium hover:bg-black/[0.09] transition-colors flex items-center justify-center gap-2"
                >
                  <span>Full Source (.tar.gz)</span>
                  <span>↗</span>
                </a>
                <span className="text-[10px] font-mono text-black/40 block text-center">Includes website & test harnesses</span>
              </div>
            </div>
          </div>
        </section>

        {/* Section 3: The 'friend' Global CLI Guide */}
        <section className="bg-white rounded-2xl border border-black/[0.08] p-8 shadow-sm space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-black/[0.06] pb-4">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-widest text-black/40">Tooling & Control</span>
              <h2 className="text-2xl font-light text-[#111] mt-0.5">The Model-Agnostic 'friend' CLI</h2>
            </div>
            <span className="font-mono text-xs bg-black/[0.04] px-3 py-1 rounded-full text-black/70">
              Installed in ~/.local/bin/friend
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-[#fafaf8] border border-black/[0.05] space-y-1.5">
              <code className="font-mono text-xs text-black font-semibold">friend start</code>
              <p className="text-xs text-black/55 leading-relaxed">Starts the 9-agent mesh with preflight healthchecks.</p>
            </div>

            <div className="p-4 rounded-xl bg-[#fafaf8] border border-black/[0.05] space-y-1.5">
              <code className="font-mono text-xs text-black font-semibold">friend model set &lt;name&gt;</code>
              <p className="text-xs text-black/55 leading-relaxed">Switches your active model (e.g. Qwen 2.5 7B, DeepSeek-R1).</p>
            </div>

            <div className="p-4 rounded-xl bg-[#fafaf8] border border-black/[0.05] space-y-1.5">
              <code className="font-mono text-xs text-black font-semibold">friend talk</code>
              <p className="text-xs text-black/55 leading-relaxed">Opens instant terminal text conversation REPL.</p>
            </div>

            <div className="p-4 rounded-xl bg-[#fafaf8] border border-black/[0.05] space-y-1.5">
              <code className="font-mono text-xs text-black font-semibold">friend status</code>
              <p className="text-xs text-black/55 leading-relaxed">Scans memory, VRAM, and Docker container health.</p>
            </div>
          </div>
        </section>

        {/* Section 4: Need Help CTA */}
        <div className="pt-4 flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-black/[0.06]">
          <p className="text-xs text-black/50">
            Have questions about GPU passthrough, Docker setup, or hardware tuning?
          </p>
          <div className="flex gap-3">
            <Link
              href="/docs/getting-started/installation"
              className="px-5 py-2.5 rounded-xl bg-white border border-black/10 text-xs font-medium text-black/80 hover:bg-[#fafaf8] transition-colors"
            >
              Read Full Install Docs →
            </Link>
            <a
              href={`${REPO_URL}/issues`}
              target="_blank"
              rel="noreferrer"
              className="px-5 py-2.5 rounded-xl bg-black/[0.04] text-xs font-medium text-black/60 hover:bg-black/[0.08] transition-colors"
            >
              GitHub Support ↗
            </a>
          </div>
        </div>
      </main>

      <SiteFooter />
    </div>
  )
}
