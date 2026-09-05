import React from "react"

type RoadmapStatus = "not-started" | "exploratory" | "in-progress"

const STATUS_LABEL: Record<RoadmapStatus, string> = {
  "not-started": "Not started",
  exploratory: "Exploratory",
  "in-progress": "In progress",
}

const STATUS_STYLE: Record<RoadmapStatus, string> = {
  "not-started": "bg-black/[0.04] text-black/50 border-black/[0.08]",
  exploratory: "bg-sky-50 text-sky-700 border-sky-200",
  "in-progress": "bg-amber-50 text-amber-800 border-amber-200",
}

interface RoadmapStatusCardProps {
  title: string
  status: RoadmapStatus
  description: string
  whyNotYet: string
}

// Deliberately plain — no blur, no fake preview UI underneath. If something
// isn't real yet, this says so directly instead of showing a mockup of it.
export function RoadmapStatusCard({ title, status, description, whyNotYet }: RoadmapStatusCardProps) {
  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-medium text-[#111]">{title}</h3>
        <span className={`font-mono text-[10px] uppercase tracking-widest px-2.5 py-1 rounded-full border ${STATUS_STYLE[status]}`}>
          {STATUS_LABEL[status]}
        </span>
      </div>
      <p className="text-sm text-black/60 leading-relaxed">{description}</p>
      <div className="pt-3 border-t border-black/[0.06]">
        <span className="text-[10px] font-mono uppercase tracking-widest text-black/35 block mb-1">Why it's not shipped</span>
        <p className="text-xs text-black/45 leading-relaxed">{whyNotYet}</p>
      </div>
    </div>
  )
}
