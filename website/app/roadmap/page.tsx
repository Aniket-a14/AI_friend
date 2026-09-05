import type { Metadata } from "next"
import { MobileNav } from "@/components/mobile-nav"
import { SiteFooter } from "@/components/site-footer"
import { RoadmapStatusCard } from "@/components/roadmap-status-card"

export const metadata: Metadata = {
  title: "Roadmap — AI Friend",
  description: "Honest status of what's not built yet — no mockups of unfinished features, just what's planned and why it isn't shipped.",
}

export default function RoadmapPage() {
  return (
    <div className="bg-[#F5F4F0] text-[#111] min-h-screen font-sans antialiased">
      <MobileNav />

      <section className="max-w-4xl mx-auto px-6 md:px-12 pt-40 pb-24">
        <div className="mb-3 inline-flex items-center gap-2 font-mono text-xs text-black/40">
          <span className="h-1.5 w-1.5 rounded-full bg-black/40" />
          Roadmap
        </div>
        <h1 className="text-4xl sm:text-5xl font-light tracking-tight mb-6" style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}>
          What's not built yet.
        </h1>
        <p className="text-base text-black/50 leading-relaxed mb-10 max-w-2xl">
          Everywhere else on this site, if a demo is shown, it's real and computes what it claims to.
          This page is the opposite: things genuinely not built, stated as such, with no preview mockup
          underneath pretending otherwise.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <RoadmapStatusCard
            title="WebGPU In-Browser Inference"
            status="exploratory"
            description="Running a quantized small LLM and ONNX voice synthesis entirely client-side, via WebAssembly + WebGPU, with no server round-trip at all."
            whyNotYet="This is a real engineering project on its own (model quantization for browser targets, WebGPU compute shader work, a completely separate inference path from the production Ollama/Rust pipeline) — not a small addition to the existing system. Nothing here has been built or benchmarked yet."
          />
          <RoadmapStatusCard
            title="1-Click Colab Training Runners"
            status="not-started"
            description="A one-click hosted notebook flow for voice fine-tuning and benchmark sweeps on free cloud GPUs, beyond the existing manual Colab notebooks already in `notebooks/`."
            whyNotYet="The manual notebooks work today and are the current supported path (see the Voice section above). Automating the click-through flow is a nice-to-have, not yet scoped or started."
          />
          <RoadmapStatusCard
            title="Community Persona Registry"
            status="not-started"
            description="A shared, opt-in registry where people could publish and browse authored persona presets beyond the built-in examples on the Showcase page."
            whyNotYet="This is a local-first, single-friend-per-person project by design (see the community product decisions in the engineering ledger) — a public registry raises real moderation, consent, and hosting questions that haven't been worked through yet, not just an engineering task."
          />
          <RoadmapStatusCard
            title="Real-Time Voice Cloning Assets in the Showcase"
            status="in-progress"
            description="Short, real GPT-SoVITS-rendered audio clips for the Voice Showcase page, replacing the current static parameter table."
            whyNotYet="Generating these requires running the actual voice pipeline against a consented voice sample and exporting clips as static assets — a content-production step, not just code. The parameter table shown today is accurate; it just doesn't play audio yet."
          />
        </div>
      </section>

      <SiteFooter />
    </div>
  )
}
