"use client"

import React, { useState, useEffect } from "react"

const STAGES = [
  {
    step: "01",
    name: "Perception",
    agent: "transport_agent",
    tech: "LiveKit WebRTC",
    latency: "15 ms",
    desc: "Ingests raw 16kHz PCM audio stream from user microphone and publishes to NATS audio.inbound.",
    signal: "audio.inbound",
  },
  {
    step: "02",
    name: "Speculation & Emotion",
    agent: "stt-agent",
    tech: "SenseVoice / ONNX",
    latency: "135 ms",
    desc: "Classifies user affect (Happy/Angry/Sad/Neutral) and detects speech onset for instantaneous reflex triggers.",
    signal: "perception.speculative",
  },
  {
    step: "03",
    name: "Reflex Interruption",
    agent: "voice-agent",
    tech: "Rust Async Engine",
    latency: "< 150 ms",
    desc: "Immediately soft-attenuates in-flight audio playback if user begins speaking mid-sentence.",
    signal: "audio.speculative_stop",
  },
  {
    step: "04",
    name: "Appraisal & Endocrine",
    agent: "brain_agent",
    tech: "PyTorch PAD Model",
    latency: "4 ms",
    desc: "Updates Russell's PAD state, calculates Cortisol/Dopamine phasic bursts, and validates immutable boundaries.",
    signal: "state.endocrine",
  },
  {
    step: "05",
    name: "Deliberation (MAUT)",
    agent: "brain_agent",
    tech: "Behavior Trees",
    latency: "12 ms",
    desc: "Scores candidate intents (Answer, Challenge, Reflect, Banter) using Multi-Attribute Utility Theory.",
    signal: "decision.intent",
  },
  {
    step: "06",
    name: "Synthesis & Streaming",
    agent: "voice-agent",
    tech: "GPT-SoVITS 32kHz",
    latency: "190 ms TTFT",
    desc: "LLM streams tokens modulated by neurochemistry directly into 32kHz physical neural voice rendering.",
    signal: "chat.output",
  },
  {
    step: "07",
    name: "Closure & Subconscious",
    agent: "subconscious_agent",
    tech: "Neo4j & ACT-R",
    latency: "Async Background",
    desc: "Records playback telemetry for tempo entrainment, updates episodic decay, and consolidates memory graph.",
    signal: "telemetry.playback",
  },
]

export function CognitiveTurnFlow() {
  const [activeStep, setActiveStep] = useState(0)
  const [autoPlay, setAutoPlay] = useState(true)

  useEffect(() => {
    if (!autoPlay) return
    const timer = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % STAGES.length)
    }, 2800)
    return () => clearInterval(timer)
  }, [autoPlay])

  const stage = STAGES[activeStep]

  return (
    <div className="rounded-2xl border border-black/[0.08] bg-white p-6 md:p-8 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 pb-6 border-b border-black/[0.06]">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/40 bg-black/[0.04] px-2.5 py-1 rounded-full">
            Cognitive Pipeline
          </span>
          <h3 className="text-2xl font-light tracking-tight mt-2 text-[#111]">
            The 7-Stage Cognitive Turn
          </h3>
          <p className="text-xs text-black/45 mt-1">
            Step through how a single human utterance traverses the decentralized multi-agent mesh.
          </p>
        </div>

        <button
          onClick={() => setAutoPlay(!autoPlay)}
          className="px-3.5 py-1.5 rounded-lg border border-black/10 text-xs font-mono text-black/60 hover:bg-black/[0.04] self-start md:self-auto transition-colors"
        >
          {autoPlay ? "⏸ Pause Animation" : "▶ Auto Play"}
        </button>
      </div>

      {/* Interactive Step Bar */}
      <div className="grid grid-cols-7 gap-2 mb-8">
        {STAGES.map((s, idx) => (
          <button
            key={s.step}
            onClick={() => {
              setActiveStep(idx)
              setAutoPlay(false)
            }}
            className={`flex flex-col items-center p-2.5 rounded-xl text-center border transition-all ${
              activeStep === idx
                ? "bg-[#111] text-white border-[#111] shadow-sm"
                : "bg-[#fafaf8] text-black/50 border-black/[0.06] hover:border-black/20 hover:text-black"
            }`}
          >
            <span className="font-mono text-[10px] tracking-wider opacity-60">{s.step}</span>
            <span className="text-xs font-light mt-0.5 truncate max-w-full hidden sm:inline">{s.name.split(" ")[0]}</span>
          </button>
        ))}
      </div>

      {/* Active Stage Detail Panel */}
      <div className="rounded-xl border border-black/[0.08] bg-[#fafaf8] p-6 grid grid-cols-1 md:grid-cols-12 gap-6">
        <div className="md:col-span-8 space-y-3">
          <div className="flex items-center gap-3">
            <span className="font-mono text-xs text-black/30 font-semibold">{stage.step} / 07</span>
            <h4 className="text-xl font-light text-[#111]">{stage.name}</h4>
          </div>
          <p className="text-sm text-black/60 leading-relaxed">{stage.desc}</p>

          <div className="pt-4 flex flex-wrap gap-4 text-xs font-mono">
            <div>
              <span className="text-black/35 block text-[10px] uppercase">Publisher Agent</span>
              <span className="text-black/80 font-medium">{stage.agent}</span>
            </div>
            <div>
              <span className="text-black/35 block text-[10px] uppercase">Engine / Technology</span>
              <span className="text-black/80 font-medium">{stage.tech}</span>
            </div>
            <div>
              <span className="text-black/35 block text-[10px] uppercase">NATS Subject</span>
              <span className="text-amber-800/80 font-medium bg-amber-50 px-2 py-0.5 rounded border border-amber-200/60">
                {stage.signal}
              </span>
            </div>
          </div>
        </div>

        <div className="md:col-span-4 flex flex-col justify-center items-center bg-white rounded-lg border border-black/[0.06] p-4 text-center">
          <span className="text-[10px] font-mono uppercase tracking-widest text-black/35 mb-1">Target Latency</span>
          <span className="text-2xl font-light text-black/90 font-mono">{stage.latency}</span>
          <span className="text-[10px] text-black/40 mt-1">Design budget, not a live measurement</span>
        </div>
      </div>
    </div>
  )
}

