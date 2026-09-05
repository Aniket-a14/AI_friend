"use client"

import React, { useMemo, useState } from "react"
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"
import { baseActivation, singleHopSpreadBoost, ACTR_DECAY_RATE_DEFAULT } from "@/lib/brain-math/memory-activation"
import { MEMORY_GRAPH_FIXTURE, type MemoryNode } from "@/lib/memory-graph-fixture"

function nodeActivation(node: MemoryNode, decayRate: number): number {
  return baseActivation({
    recallCount: node.recallCount,
    hoursSince: node.hoursSince,
    importanceScore: node.importanceScore,
    distEmo: node.distEmo,
    spacingHours: node.recallCount >= 2 ? node.hoursSince / node.recallCount : null,
    decayRate,
  })
}

const TOPIC_COLORS: Record<string, string> = {
  work: "#2563eb",
  family: "#db2777",
  hobbies: "#059669",
  friendship: "#d97706",
  self: "#7c3aed",
}

export function MemoryActivationVisualizer() {
  const [recallCount, setRecallCount] = useState(3)
  const [hoursSince, setHoursSince] = useState(48)
  const [importance, setImportance] = useState(0.6)
  const [distEmo, setDistEmo] = useState(0.4)
  const [queriedNodeId, setQueriedNodeId] = useState<string | null>(null)

  const decayCurve = useMemo(() => {
    const points = []
    for (let h = 1; h <= 24 * 30; h += 24) {
      points.push({
        hours: h,
        days: Math.round(h / 24),
        massed: baseActivation({ recallCount, hoursSince: h, importanceScore: importance, distEmo, spacingHours: recallCount >= 2 ? 1 : null }),
        spaced: baseActivation({ recallCount, hoursSince: h, importanceScore: importance, distEmo, spacingHours: recallCount >= 2 ? h / recallCount : null }),
      })
    }
    return points
  }, [recallCount, hoursSince, importance, distEmo])

  const nodesWithActivation = useMemo(() => {
    const base = MEMORY_GRAPH_FIXTURE.map((n) => ({ ...n, activation: nodeActivation(n, ACTR_DECAY_RATE_DEFAULT) }))
    if (!queriedNodeId) return base
    const queried = base.find((n) => n.id === queriedNodeId)
    if (!queried) return base
    const boost = singleHopSpreadBoost(queried.activation, queried.neighbors.length)
    return base.map((n) =>
      queried.neighbors.includes(n.id) ? { ...n, activation: n.activation + boost, boosted: true } : n,
    )
  }, [queriedNodeId])

  const maxAct = Math.max(...nodesWithActivation.map((n) => n.activation))
  const minAct = Math.min(...nodesWithActivation.map((n) => n.activation))

  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm">
      <div className="mb-6 pb-6 border-b border-black/[0.06]">
        <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 bg-black/[0.04] px-2.5 py-1 rounded-full">
          Live Simulator
        </span>
        <h3 className="text-2xl font-light tracking-tight mt-2 text-[#111]">
          Memory Activation & Decay
        </h3>
        <p className="text-xs text-black/45 mt-1 max-w-2xl">
          Exact port of the ACT-R base-level activation formula shared by every retrieval path in the real
          system: <code className="text-[11px]">ln(freq) − d·ln(recency) + importance + emotional-proximity + spacing</code>.
          The graph below is illustrative fixture data (not a real conversation), but the activation score on
          every node is computed live from this formula.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-5 space-y-4">
          <div className="p-3 rounded-lg border border-black/[0.06] bg-[#fafaf8]">
            <div className="flex justify-between text-[11px] mb-1"><span className="font-medium text-black/70">Recall Count</span><span className="font-mono">{recallCount}</span></div>
            <input type="range" min={1} max={15} step={1} value={recallCount} onChange={(e) => setRecallCount(parseInt(e.target.value))} className="w-full accent-black h-1" />
          </div>
          <div className="p-3 rounded-lg border border-black/[0.06] bg-[#fafaf8]">
            <div className="flex justify-between text-[11px] mb-1"><span className="font-medium text-black/70">Hours Since Last Recall</span><span className="font-mono">{hoursSince}h</span></div>
            <input type="range" min={1} max={720} step={1} value={hoursSince} onChange={(e) => setHoursSince(parseInt(e.target.value))} className="w-full accent-black h-1" />
          </div>
          <div className="p-3 rounded-lg border border-black/[0.06] bg-[#fafaf8]">
            <div className="flex justify-between text-[11px] mb-1"><span className="font-medium text-black/70">Importance Score</span><span className="font-mono">{importance.toFixed(2)}</span></div>
            <input type="range" min={0} max={1} step={0.05} value={importance} onChange={(e) => setImportance(parseFloat(e.target.value))} className="w-full accent-black h-1" />
          </div>
          <div className="p-3 rounded-lg border border-black/[0.06] bg-[#fafaf8]">
            <div className="flex justify-between text-[11px] mb-1"><span className="font-medium text-black/70">Emotional Distance (0=matches current mood)</span><span className="font-mono">{distEmo.toFixed(2)}</span></div>
            <input type="range" min={0} max={1} step={0.05} value={distEmo} onChange={(e) => setDistEmo(parseFloat(e.target.value))} className="w-full accent-black h-1" />
          </div>

          <div className="rounded-xl border border-black/[0.07] bg-[#fafaf8] p-4">
            <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 block mb-2">Massed vs. Spaced Recall</span>
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={decayCurve}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
                <XAxis dataKey="days" tick={{ fontSize: 9 }} label={{ value: "days since recall", fontSize: 9, position: "insideBottom", offset: -2 }} />
                <YAxis tick={{ fontSize: 9 }} />
                <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                <Line type="monotone" dataKey="massed" stroke="#94a3b8" strokeWidth={2} dot={false} name="Massed (all recalls in 1h)" />
                <Line type="monotone" dataKey="spaced" stroke="#2563eb" strokeWidth={2} dot={false} name="Spaced (spread evenly)" />
              </LineChart>
            </ResponsiveContainer>
            <p className="text-[10px] text-black/40 mt-1">Same frequency and recency — spaced practice still wins, the literature's central spacing-effect finding.</p>
          </div>
        </div>

        <div className="lg:col-span-7 rounded-xl border border-black/[0.07] bg-[#fafaf8] p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-mono uppercase tracking-widest text-black/40">
              Illustrative Memory Graph (click a node to query it)
            </span>
            {queriedNodeId && (
              <button onClick={() => setQueriedNodeId(null)} className="text-[10px] text-black/40 hover:text-black/70">
                Clear query
              </button>
            )}
          </div>
          <div className="grid grid-cols-5 sm:grid-cols-8 lg:grid-cols-10 gap-2 max-h-[360px] overflow-y-auto pr-1">
            {nodesWithActivation.map((n: any) => {
              const norm = maxAct === minAct ? 0.5 : (n.activation - minAct) / (maxAct - minAct)
              return (
                <button
                  key={n.id}
                  onClick={() => setQueriedNodeId(n.id)}
                  title={`${n.label} — activation ${n.activation.toFixed(2)}`}
                  className={`aspect-square rounded-lg border transition-all ${
                    n.id === queriedNodeId ? "ring-2 ring-black" : n.boosted ? "ring-2 ring-amber-400" : ""
                  }`}
                  style={{
                    backgroundColor: TOPIC_COLORS[n.topic],
                    opacity: 0.25 + norm * 0.75,
                    borderColor: "rgba(0,0,0,0.08)",
                  }}
                />
              )
            })}
          </div>
          <div className="flex flex-wrap gap-3 mt-4 text-[10px]">
            {Object.entries(TOPIC_COLORS).map(([topic, color]) => (
              <span key={topic} className="flex items-center gap-1.5 text-black/50">
                <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                {topic}
              </span>
            ))}
          </div>
          <p className="text-[11px] text-black/45 mt-3 leading-relaxed">
            Brightness is each node's live ACT-R activation. Clicking a node simulates querying it: its
            direct neighbors (amber ring) get a one-hop spreading-activation boost — a simplified stand-in
            for the real system's Personalized-PageRank graph boost, not a literal port of that iterative
            algorithm.
          </p>
        </div>
      </div>
    </div>
  )
}
