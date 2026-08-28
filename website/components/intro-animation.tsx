"use client"

import { useEffect, useState } from "react"

const LETTERS = ["P", "A", "L", "A", "B", "S"]
const CAPTION = "Bring your friend to life!"

const LETTER_IN_STAGGER  = 90    // ms between each letter appearing
const LETTER_IN_DUR      = 700   // duration of each letter appear transition
const HOLD_DURATION      = 1000  // hold fully visible (letters + caption) before exit
const LETTERS_IN_TOTAL   = LETTER_IN_STAGGER * (LETTERS.length - 1) + LETTER_IN_DUR + HOLD_DURATION

// Caption starts fading in once the last letter has landed
const CAPTION_DELAY      = LETTER_IN_STAGGER * (LETTERS.length - 1) + LETTER_IN_DUR
const CAPTION_IN_DUR     = 500

const LETTER_OUT_STAGGER = 55    // ms between each letter disappearing
const LETTER_OUT_DUR     = 450   // duration of each letter fade out
const LETTERS_OUT_TOTAL  = LETTER_OUT_STAGGER * (LETTERS.length - 1) + LETTER_OUT_DUR

const CURTAIN_DELAY      = LETTERS_IN_TOTAL + 100
const CURTAIN_DURATION   = 1300  // matches the CSS transition on the curtain div
const ANIM_TOTAL         = CURTAIN_DELAY + LETTERS_OUT_TOTAL + 1400

// Exported: moment the curtain finishes retracting — when the bg is fully visible
export const INTRO_DURATION_MS = CURTAIN_DELAY + CURTAIN_DURATION
// Exported: ms before curtain fully done to start hero animations (overlap for smoothness)
export const HERO_REVEAL_MS = CURTAIN_DELAY + CURTAIN_DURATION - 150

type Phase = "idle" | "in" | "out" | "done"

export function IntroAnimation({ onDone }: { onDone: () => void }) {
  const [phase, setPhase] = useState<Phase>("idle")
  const [curtainUp, setCurtainUp] = useState(false)

  useEffect(() => {
    // Tiny delay so the browser has painted before we start transitioning
    const t0 = setTimeout(() => setPhase("in"), 80)
    const t1 = setTimeout(() => setPhase("out"), LETTERS_IN_TOTAL)
    const t2 = setTimeout(() => setCurtainUp(true), CURTAIN_DELAY)
    const t3 = setTimeout(() => onDone(), HERO_REVEAL_MS)
    const t4 = setTimeout(() => setPhase("done"), ANIM_TOTAL)

    return () => { clearTimeout(t0); clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4) }
  }, [onDone])

  if (phase === "done") return null

  const isIdle = phase === "idle"
  const isIn   = phase === "in"
  const isOut  = phase === "out"

  return (
    <div className="fixed inset-0 z-[100] pointer-events-none" aria-hidden="true">

      {/* Gradient curtain — retracts upward, revealing mountains from bottom */}
      <div
        className="absolute inset-x-0 top-0"
        style={{
          bottom: curtainUp ? "100%" : "0%",
          transition: curtainUp ? "bottom 1.3s cubic-bezier(0.76, 0, 0.24, 1)" : "none",
          background: "#f5f4f1",
        }}
      />

      {/* PALABS letters + caption */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="flex" style={{ gap: "0.06em" }}>
          {LETTERS.map((letter, i) => {
            const inDelay  = i * LETTER_IN_STAGGER
            const outDelay = i * LETTER_OUT_STAGGER

            const opacity    = isIdle ? 0 : isIn ? 1 : 0
            const blur       = isIdle ? 36 : isIn ? 0 : 24
            const translateY = isIdle ? 48 : isIn ? 0 : -20

            const transition = isOut
              ? `opacity ${LETTER_OUT_DUR}ms cubic-bezier(0.4,0,1,1) ${outDelay}ms,
                 filter  ${LETTER_OUT_DUR}ms cubic-bezier(0.4,0,1,1) ${outDelay}ms,
                 transform ${LETTER_OUT_DUR}ms cubic-bezier(0.4,0,1,1) ${outDelay}ms`
              : isIn
              ? `opacity ${LETTER_IN_DUR}ms cubic-bezier(0.16,1,0.3,1) ${inDelay}ms,
                 filter  ${LETTER_IN_DUR}ms cubic-bezier(0.16,1,0.3,1) ${inDelay}ms,
                 transform ${LETTER_IN_DUR}ms cubic-bezier(0.16,1,0.3,1) ${inDelay}ms`
              : "none"

            return (
              <span
                key={i}
                className="font-sans font-bold text-[#111] leading-none select-none"
                style={{
                  fontSize: `calc((100vw - 64px) / ${LETTERS.length})`,
                  letterSpacing: "0.05em",
                  opacity,
                  filter: `blur(${blur}px)`,
                  transform: `translateY(${translateY}px)`,
                  transition,
                  willChange: "opacity, filter, transform",
                }}
              >
                {letter}
              </span>
            )
          })}
        </div>

        <p
          className="font-sans text-sm sm:text-base text-black/45 tracking-wide mt-4 sm:mt-6 select-none"
          style={{
            opacity: isIn ? 1 : 0,
            filter: `blur(${isIn ? 0 : 12}px)`,
            transform: `translateY(${isIn ? 0 : 12}px)`,
            transition: isOut
              ? `opacity ${LETTER_OUT_DUR}ms cubic-bezier(0.4,0,1,1), filter ${LETTER_OUT_DUR}ms cubic-bezier(0.4,0,1,1), transform ${LETTER_OUT_DUR}ms cubic-bezier(0.4,0,1,1)`
              : isIn
              ? `opacity ${CAPTION_IN_DUR}ms cubic-bezier(0.16,1,0.3,1) ${CAPTION_DELAY}ms, filter ${CAPTION_IN_DUR}ms cubic-bezier(0.16,1,0.3,1) ${CAPTION_DELAY}ms, transform ${CAPTION_IN_DUR}ms cubic-bezier(0.16,1,0.3,1) ${CAPTION_DELAY}ms`
              : "none",
            willChange: "opacity, filter, transform",
          }}
        >
          {CAPTION}
        </p>
      </div>

    </div>
  )
}
