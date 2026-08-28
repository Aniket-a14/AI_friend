import Link from "next/link"
import { REPO_URL } from "@/lib/site"

export function SiteFooter() {
  return (
    <footer className="py-16 px-6 md:px-12 lg:px-20 border-t border-black/[0.08] bg-[#fafaf8] text-[#111]">
      <div className="max-w-6xl mx-auto grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-8 mb-12">
        {/* Col 1: Product */}
        <div className="space-y-3">
          <span className="font-mono text-[10px] tracking-widest uppercase text-black/40 block">Product</span>
          <ul className="space-y-2 text-xs">
            <li><Link href="/playground" className="text-black/60 hover:text-black transition-colors">Interactive Playground</Link></li>
            <li><Link href="/#how" className="text-black/60 hover:text-black transition-colors">How It's Different</Link></li>
            <li><Link href="/#mesh" className="text-black/60 hover:text-black transition-colors">Architecture Mesh</Link></li>
            <li><Link href="/showcase" className="text-black/60 hover:text-black transition-colors">Persona Showcase</Link></li>
            <li><Link href="/#setup" className="text-black/60 hover:text-black transition-colors">Quick Setup</Link></li>
          </ul>
        </div>

        {/* Col 2: Research & Comparison */}
        <div className="space-y-3">
          <span className="font-mono text-[10px] tracking-widest uppercase text-black/40 block">Research & Data</span>
          <ul className="space-y-2 text-xs">
            <li><Link href="/benchmarks" className="text-black/60 hover:text-black transition-colors">Hardware Benchmarks</Link></li>
            <li><Link href="/comparison" className="text-black/60 hover:text-black transition-colors">Assistant Comparison</Link></li>
            <li><Link href="/research" className="text-black/60 hover:text-black transition-colors">Cognitive Science</Link></li>
            <li><Link href="/changelog" className="text-black/60 hover:text-black transition-colors">Changelog & Roadmap</Link></li>
          </ul>
        </div>

        {/* Col 3: Documentation */}
        <div className="space-y-3">
          <span className="font-mono text-[10px] tracking-widest uppercase text-black/40 block">Documentation</span>
          <ul className="space-y-2 text-xs">
            <li><Link href="/docs/getting-started/installation" className="text-black/60 hover:text-black transition-colors">Installation Guide</Link></li>
            <li><Link href="/docs/getting-started/quickstart" className="text-black/60 hover:text-black transition-colors">Quickstart</Link></li>
            <li><Link href="/docs/concepts/architecture" className="text-black/60 hover:text-black transition-colors">Mesh Architecture</Link></li>
            <li><Link href="/docs/api-reference/rest-endpoints" className="text-black/60 hover:text-black transition-colors">REST API Spec</Link></li>
            <li><Link href="/docs/api-reference/websocket-protocol" className="text-black/60 hover:text-black transition-colors">WebSocket Spec</Link></li>
          </ul>
        </div>

        {/* Col 4: Operations & Guides */}
        <div className="space-y-3">
          <span className="font-mono text-[10px] tracking-widest uppercase text-black/40 block">Guides & Ops</span>
          <ul className="space-y-2 text-xs">
            <li><Link href="/docs/guides/voice-training" className="text-black/60 hover:text-black transition-colors">GPU Voice Training</Link></li>
            <li><Link href="/docs/guides/colab-gpu-acceleration" className="text-black/60 hover:text-black transition-colors">Colab Acceleration</Link></li>
            <li><Link href="/docs/guides/backup-migration" className="text-black/60 hover:text-black transition-colors">Backup & Disaster Recovery</Link></li>
            <li><Link href="/docs/testing/eval-harness" className="text-black/60 hover:text-black transition-colors">Eval Harness</Link></li>
            <li><Link href="/docs/troubleshooting/common-issues" className="text-black/60 hover:text-black transition-colors">Troubleshooting</Link></li>
          </ul>
        </div>

        {/* Col 5: Community & Legal */}
        <div className="space-y-3">
          <span className="font-mono text-[10px] tracking-widest uppercase text-black/40 block">Community</span>
          <ul className="space-y-2 text-xs">
            <li><Link href="/about" className="text-black/60 hover:text-black transition-colors">About AI Friend</Link></li>
            <li><a href={REPO_URL} target="_blank" rel="noopener noreferrer" className="text-black/60 hover:text-black transition-colors">GitHub Repository ↗</a></li>
            <li><a href={`${REPO_URL}/blob/main/LICENSE`} target="_blank" rel="noopener noreferrer" className="text-black/60 hover:text-black transition-colors">MIT License ↗</a></li>
            <li><a href={`${REPO_URL}/blob/main/SECURITY.md`} target="_blank" rel="noopener noreferrer" className="text-black/60 hover:text-black transition-colors">Security Policy ↗</a></li>
            <li><a href={`${REPO_URL}/blob/main/CONTRIBUTING.md`} target="_blank" rel="noopener noreferrer" className="text-black/60 hover:text-black transition-colors">Contributing ↗</a></li>
          </ul>
        </div>
      </div>

      <div className="max-w-6xl mx-auto pt-8 border-t border-black/[0.06] flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-semibold tracking-[0.25em] text-[#111]">AI FRIEND</span>
          <span className="text-xs text-black/35 font-light">· An open-source, local-first Cognitive Voice System.</span>
        </div>
        <span className="text-xs text-black/40">MIT Licensed. 100% Data Sovereignty.</span>
      </div>
    </footer>
  )
}
