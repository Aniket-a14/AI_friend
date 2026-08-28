"use client"

import { useEffect, useId, useState } from "react"

export function MermaidDiagram({ chart }: { chart: string }) {
  const rawId = useId().replace(/:/g, "")
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    import("mermaid").then(async (mod) => {
      const mermaid = mod.default
      mermaid.initialize({
        startOnLoad: false,
        theme: "neutral",
        securityLevel: "strict",
        fontFamily: '"IBM Plex Sans", sans-serif',
      })
      try {
        const { svg: rendered } = await mermaid.render(`mermaid-${rawId}`, chart)
        if (!cancelled) setSvg(rendered)
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to render diagram")
      }
    })

    return () => {
      cancelled = true
    }
  }, [chart, rawId])

  if (error) {
    return (
      <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 text-xs text-red-700">
        Diagram failed to render: {error}
      </div>
    )
  }

  if (!svg) {
    return <div className="mb-4 h-32 animate-pulse rounded-xl border border-black/[0.07] bg-black/[0.03]" />
  }

  return (
    <div
      className="mb-4 flex justify-center overflow-x-auto rounded-xl border border-black/[0.07] bg-white p-4 [&_svg]:max-w-full"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
