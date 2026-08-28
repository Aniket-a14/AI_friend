"use client"

import React from "react"

const SECURITY_PILLARS = [
  {
    title: "100% Local Confinement",
    tag: "ZERO EGRESS",
    desc: "PostgreSQL, Neo4j, Redis, Qdrant, NATS, Ollama, and LiveKit bind exclusively to 127.0.0.1 loopback interfaces.",
    benefit: "Zero conversation text, audio, or vector embeddings leave your hardware.",
  },
  {
    title: "RBAC JetStream Isolation",
    tag: "LEAST PRIVILEGE",
    desc: "Every NATS client operates under scoped user accounts with restricted publish/subscribe topic permissions.",
    benefit: "Prevents unauthorized agents from reading sensitive system subjects.",
  },
  {
    title: "4-Store Atomic Snapshots",
    tag: "PORTABILITY",
    desc: "Single-command export script captures PostgreSQL JSONL, Neo4j Cypher, and SQLite affect state into an encrypted archive.",
    benefit: "Total disaster recovery and seamless migration across workstations.",
  },
  {
    title: "Immutable Safety Floor",
    tag: "CONSTITUTIONAL",
    desc: "Tier 0 hardcoded boundaries (Honesty, Privacy, Anti-Harm) enforced before any user prompt can reach the LLM.",
    benefit: "Guarantees system credentials and private files cannot be exfiltrated.",
  },
  {
    title: "Zero Account Tracking",
    tag: "NO TELEMETRY",
    desc: "The entire codebase contains zero tracking scripts, analytics pixels, or phone-home logging.",
    benefit: "Complete anonymity with true self-hosted ownership.",
  },
  {
    title: "Permissive MIT License",
    tag: "OPEN SOURCE",
    desc: "Full transparency under the MIT license with public audit reports, mutation tests, and CI workflows.",
    benefit: "Freedom to inspect, fork, modify, and extend without commercial lock-in.",
  },
]

export function SecurityComplianceGrid() {
  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm">
      <div className="mb-6 pb-6 border-b border-black/[0.06]">
        <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 bg-black/[0.04] px-2.5 py-1 rounded-full">
          Data Sovereignty
        </span>
        <h3 className="text-2xl font-light tracking-tight mt-2 text-[#111]">
          Security, Privacy & Local Confinement
        </h3>
        <p className="text-xs text-black/45 mt-1">
          Designed for developers and researchers who demand verified local containment without cloud data leaks.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {SECURITY_PILLARS.map((p) => (
          <div key={p.title} className="p-5 rounded-xl border border-black/[0.06] bg-[#fafaf8] flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-[9px] uppercase tracking-wider text-black/40 bg-black/[0.04] px-2 py-0.5 rounded">
                  {p.tag}
                </span>
              </div>
              <h4 className="text-base font-light text-black/90 mb-2">{p.title}</h4>
              <p className="text-xs text-black/50 leading-relaxed mb-4">{p.desc}</p>
            </div>
            <div className="pt-3 border-t border-black/[0.04] text-[11px] text-emerald-700/90 font-medium">
              ✓ {p.benefit}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

