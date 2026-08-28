"use client"

import React, { useState, useEffect } from "react"

export function OSInstallTabs() {
  const [selectedOS, setSelectedOS] = useState<"mac" | "linux" | "windows" | "docker">("mac")
  const [customModel, setCustomModel] = useState<string>("llama3.2:3b")
  const [isCloud, setIsCloud] = useState<boolean>(false)
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

  // Dynamic model parameter flag if custom model specified
  const modelFlag = customModel.trim() && customModel.trim() !== "llama3.2:3b"
    ? ` --model ${customModel.trim()}`
    : ""

  const installCommands = {
    mac: `curl -fsSL https://raw.githubusercontent.com/Aniket-a14/AI_friend/main/scripts/install.sh | bash -s --${modelFlag}`,
    linux: `curl -fsSL https://raw.githubusercontent.com/Aniket-a14/AI_friend/main/scripts/install.sh | bash -s --${modelFlag}`,
    windows: `& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Aniket-a14/AI_friend/main/scripts/install.ps1)))${modelFlag}`,
    docker: `git clone https://github.com/Aniket-a14/AI_friend.git && cd AI_friend && ./start.sh`,
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

      {/* Freeform Model Selection: Any Local or Cloud Model */}
      <div className="space-y-3 bg-[#fafaf8] p-5 rounded-2xl border border-black/[0.06]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <label className="text-xs font-semibold text-black/90 block">
              Enter Any Model Name (Local or Cloud)
            </label>
            <p className="text-[11px] text-black/50 mt-0.5">
              100% Model-Agnostic: Type any Ollama tag, fine-tuned GGUF weights, or cloud model API.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsCloud(false)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-mono transition-colors ${
                !isCloud ? "bg-[#111] text-white" : "bg-black/[0.05] text-black/60 hover:bg-black/[0.08]"
              }`}
            >
              Local Engine (Ollama)
            </button>
            <button
              onClick={() => setIsCloud(true)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-mono transition-colors ${
                isCloud ? "bg-[#111] text-white" : "bg-black/[0.05] text-black/60 hover:bg-black/[0.08]"
              }`}
            >
              Cloud Provider (API)
            </button>
          </div>
        </div>

        <div className="relative">
          <input
            type="text"
            value={customModel}
            onChange={(e) => setCustomModel(e.target.value)}
            placeholder={isCloud ? "e.g. claude-3-5-sonnet, gpt-4o, openrouter/meta-llama/llama-3.3-70b" : "e.g. llama3.2:3b, qwen2.5:14b, deepseek-r1:32b, mistral:7b"}
            className="w-full px-4 py-3 rounded-xl border border-black/[0.1] bg-white text-xs sm:text-sm font-mono text-black placeholder:text-black/30 focus:outline-none focus:ring-1 focus:ring-black/25 shadow-2xs"
          />
          {customModel && (
            <button
              onClick={() => setCustomModel("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-black/40 hover:text-black"
            >
              ✕
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] font-mono text-black/45">
          <span>Active Model: <strong className="text-black/80 font-mono">{customModel.trim() || "(default: llama3.2:3b)"}</strong></span>
          <span>Switch anytime later with: <code className="bg-black/[0.04] px-1 py-0.5 rounded text-black/70">friend model set &lt;name&gt;</code></span>
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
          <span className="font-mono text-[10px] uppercase text-black/40 block font-semibold">1. Complete Freedom</span>
          <p className="text-xs text-black/60 leading-relaxed">
            Runs any model from Ollama, vLLM, HuggingFace, Anthropic, or OpenAI. No vendor lock-in.
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-black/[0.05] space-y-1">
          <span className="font-mono text-[10px] uppercase text-black/40 block font-semibold">2. Lightweight Runtime</span>
          <p className="text-xs text-black/60 leading-relaxed">
            Installer downloads only the 4.3 MB runtime package without cloning the full repository.
          </p>
        </div>

        <div className="p-3.5 rounded-xl bg-[#fafaf8] border border-black/[0.05] space-y-1">
          <span className="font-mono text-[10px] uppercase text-black/40 block font-semibold">3. Global Tooling</span>
          <p className="text-xs text-black/60 leading-relaxed">
            Manage models, voices, and chat through the global <code className="font-mono text-[11px] bg-black/[0.04] px-1 rounded">friend</code> command.
          </p>
        </div>
      </div>
    </div>
  )
}
