"use client"

import React from "react"

interface ComingSoonOverlayProps {
  children?: React.ReactNode
  title?: string
  description?: string
  eta?: string
  className?: string
  blurAmount?: "sm" | "md" | "lg"
}

export function ComingSoonOverlay({
  children,
  title = "COMING SOON",
  description = "In active development as part of the community roadmap.",
  eta,
  className = "",
  blurAmount = "md",
}: ComingSoonOverlayProps) {
  const blurClasses = {
    sm: "backdrop-blur-xs bg-white/40",
    md: "backdrop-blur-sm bg-[#F5F4F0]/50",
    lg: "backdrop-blur-md bg-[#F5F4F0]/65",
  }[blurAmount]

  return (
    <div className={`relative overflow-hidden rounded-2xl group ${className}`}>
      {/* Underlying content - visible through glossy blur and non-interactive */}
      <div className="pointer-events-none select-none filter blur-[1.5px] opacity-70 transition-all duration-300">
        {children}
      </div>

      {/* Glossy Frosted Glass Overlay */}
      <div
        className={`absolute inset-0 z-20 flex flex-col items-center justify-center p-6 text-center ${blurClasses} border border-white/60 shadow-[inset_0_1px_1px_rgba(255,255,255,0.6),0_8px_24px_rgba(0,0,0,0.04)]`}
        style={{
          backdropFilter: "blur(6px)",
          WebkitBackdropFilter: "blur(6px)",
        }}
      >
        {/* Sleek Pill Badge */}
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#111] text-white shadow-md mb-2.5">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] font-semibold">
            {title}
          </span>
          {eta && (
            <span className="text-[9px] font-mono text-white/50 border-l border-white/20 pl-2">
              {eta}
            </span>
          )}
        </div>

        {description && (
          <p className="text-xs text-black/65 max-w-xs font-sans leading-relaxed">
            {description}
          </p>
        )}
      </div>
    </div>
  )
}
