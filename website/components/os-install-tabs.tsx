"use client"

import React, { useState, useEffect } from "react"

export function OSInstallTabs() {
  const [selectedOS, setSelectedOS] = useState<"mac" | "linux" | "windows" | "docker">("mac")
  const [selectedModel, setSelectedModel] = useState<string>("llama3.2:3b")
  const [copied, setCopied] = useState(false)

  // Client-side automatic OS detection
  useEffect(() => {
    if (typeof window === "undefined") return
    const ua = window.navigator.userAgent.toLowerCase()
    if (ua.includes("win")) {
      setSelectedOS("windows")
    } else if (ua.includes("linux")) {
      setSelectedOS("linux")
    } else if (ua.includes("mac")) {
      setSelectedOS("mac")
    }
  }, [])

  const installCommands = {
    mac: `curl -fsSL https://raw.githubusercontent.com/Aniket-a14/AI_friend/main/scripts/install.sh | bash`,
    linux: `curl -fsSL https://raw.githubusercontent.com/Aniket-a14/AI_friend/main/scripts/install.sh | bash`,
    windows: `irm https://raw.githubusercontent.com/Aniket-a14/AI_friend/main/scripts/install.ps1 | iex`,
    docker: `git clone https://github.com/Aniket-a14/AI_friend.git && cd AI_friend && ./start.sh`,
  }

  const modelFlags = {
    "llama3.2:3b": "",
    "qwen2.5:7b": " --model qwen2.5:7b",
    "deepseek-r1:7b": " --model deepseek-r1:7b",
    "llama3.2:1b": " --model llama3.2:1b",
    "claude-3-5-sonnet": " --model claude-3-5-sonnet",
  }

  const activeCommand = installCommands[selectedOS]

  const handleCopy = () => {
    navigator.clipboard.writeText(activeCommand)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm space-y-6">
      {/* OS Tab Selector */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-black/[0.06] pb-4">
        <div className="flex flex-wrap gap-1.5">
          {[
            { id: "mac", label: "macOS (Apple Silicon / Intel)", icon: "" },
            { id: "windows", label: "Windows 10/11 (PowerShell)", icon: "⊞" },
            { id: "linux", label: "Linux (Ubuntu / Arch / Fedora)", icon: "🐧" },
            { id: "docker", label: "Docker Compose (Direct)", icon: "🐳" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSelectedOS(tab.id as any)}
              className={`px-3.5 py-2 rounded-xl text-xs transition-all flex items-center gap-1.5 ${
                selectedOS === tab.id
                  ? "bg-[#111] text-white shadow-xs font-medium"
                  : "bg-black/[0.04] text-black/60 hover:bg-black/[0.07]"
              }`}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        <span className="text-[10px] font-mono text-emerald-800 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
          ● Auto-Detected Recommended
        </span>
      </div>

      {/* Model Choice Pill Selector */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-[11px] font-mono uppercase tracking-wider text-black/40">
            Choose Your Brain Model (Model-Agnostic)
          </label>
          <span className="text-[10px] text-black/40 font-mono">Switch anytime with: friend model set &lt;name&gt;</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {[
            { id: "llama3.2:3b", name: "Llama 3.2 3B", badge: "Default", vram: "2.0 GB" },
            { id: "qwen2.5:7b", name: "Qwen 2.5 7B", badge: "Reasoning", vram: "4.7 GB" },
            { id: "deepseek-r1:7b", name: "DeepSeek-R1 7B", badge: "CoT Think", vram: "4.7 GB" },
            { id: "llama3.2:1b", name: "Llama 3.2 1B", badge: "Lightweight", vram: "1.1 GB" },
            { id: "claude-3-5-sonnet", name: "Claude 3.5 Sonnet", badge: "Cloud API", vram: "0 GB (API)" },
          ].map((m) => (
            <button
              key={m.id}
              onClick={() => setSelectedModel(m.id)}
              className={`p-3 rounded-xl border text-left transition-all flex flex-col justify-between ${
                selectedModel === m.id
                  ? "border-[#111] bg-[#fafaf8] shadow-xs"
                  : "border-black/[0.06] bg-white hover:bg-[#fafaf8]"
              }`}
            >
              <div>
                <span className="text-xs font-semibold text-black/90 block">{m.name}</span>
                <span className="text-[10px] text-black/40 font-mono mt-0.5 block">{m.vram}</span>
              </div>
              <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded self-start mt-2 ${
                selectedModel === m.id ? "bg-[#111] text-white" : "bg-black/[0.04] text-black/60"
              }`}>
                {m.badge}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Terminal Code Copy Block */}
      <div className="rounded-xl border border-black/[0.08] bg-[#111] text-white p-4 font-mono text-xs shadow-inner space-y-3">
        <div className="flex items-center justify-between text-white/40 text-[10px] border-b border-white/10 pb-2">
          <span>{selectedOS === "windows" ? "PowerShell (Administrator)" : "Terminal (Bash/Zsh)"}</span>
          <button
            onClick={handleCopy}
            className="px-2.5 py-1 rounded bg-white/10 hover:bg-white/20 text-white transition-colors flex items-center gap-1 text-[11px]"
          >
            <span>{copied ? "✓ Copied" : "Copy Command"}</span>
          </button>
        </div>

        <div className="flex items-center gap-2 text-emerald-400 overflow-x-auto py-1">
          <span className="text-white/40 select-none">$</span>
          <code className="text-white selection:bg-white/20 whitespace-nowrap">
            {activeCommand}
          </code>
        </div>
      </div>

      {/* OS Specific Guidance & Post-Install */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
        <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-black/[0.05] space-y-1">
          <span className="font-mono text-[10px] uppercase text-black/40 block font-semibold">1. Prerequisites</span>
          <p className="text-xs text-black/60 leading-relaxed">
            {selectedOS === "mac" && "Requires macOS 13+, Docker Desktop, and Python 3.11+."}
            {selectedOS === "windows" && "Requires Windows 10/11, Docker Desktop (WSL2), and PowerShell."}
            {selectedOS === "linux" && "Requires Linux x86_64 or aarch64, Docker Engine, and Python 3.11+."}
            {selectedOS === "docker" && "Runs all 9 agents inside Docker without local build toolchains."}
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-black/[0.05] space-y-1">
          <span className="font-mono text-[10px] uppercase text-black/40 block font-semibold">2. Global Command</span>
          <p className="text-xs text-black/60 leading-relaxed">
            Installs global <code className="font-mono text-[11px] bg-black/[0.04] px-1 rounded">friend</code> command to launch, chat, and configure at any time.
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-black/[0.05] space-y-1">
          <span className="font-mono text-[10px] uppercase text-black/40 block font-semibold">3. Model Freedom</span>
          <p className="text-xs text-black/60 leading-relaxed">
            Selected: <strong className="text-black/80">{selectedModel}</strong>. Switch models anytime via <code className="font-mono text-[10px] bg-black/[0.04] px-1 rounded">friend model set</code>.
          </p>
        </div>
      </div>
    </div>
  )
}

