// Exact 1:1 port of backend/app/persona/compiler.py's _infer_temperament
// (lines 115-259) -- the deterministic arithmetic that turns 9 scored
// dimensions into bounded PersonaProfile fields. Does NOT port compile_persona
// itself: turning freeform prose into these 9 scores is a real LLM call in the
// actual product, not reproduced here.

export interface PersonaDimensions {
  /** -1.0 (cold) to 1.0 (warm) */
  warmth: number
  /** 0.0 (calm) to 1.0 (excitable) */
  energy: number
  /** 0.0 (yielding) to 1.0 (take-charge) */
  assertiveness: number
  /** 0.0 (even-keeled) to 1.0 (reactive) */
  volatility: number
  /** 0.0 (dwells on things) to 1.0 (bounces back quickly) */
  resilience: number
  /** 0.0 (easily swayed) to 1.0 (stubborn/consistent) */
  opinionFirmness: number
  /** 0.0 (guarded) to 1.0 (quick-to-trust) */
  opennessToTrust: number
  /** 0.0 (standoffish long-term) to 1.0 (quickly-attached) */
  warmthGrowth: number
  /** 0.0 (brief reactions) to 1.0 (lingering reactions) */
  emotionalLingering: number
}

export const DEFAULT_DIMENSIONS: PersonaDimensions = {
  warmth: 0.0,
  energy: 0.5,
  assertiveness: 0.5,
  volatility: 0.5,
  resilience: 0.5,
  opinionFirmness: 0.5,
  opennessToTrust: 0.5,
  warmthGrowth: 0.5,
  emotionalLingering: 0.5,
}

export interface CompiledPersonaFields {
  baselineValence: number
  baselineArousal: number
  baselineDominance: number
  valenceDriftRate: number
  arousalResponseRate: number
  dominanceStability: number
  trustChangeRate: number
  attachmentGrowthRate: number
  moodDecayRate: number
  dopamineHalflifeS: number
  cortisolHalflifeS: number
  adrenalineHalflifeS: number
  initialTrust: number
  initialAttachment: number
}

export interface Inference {
  field: keyof CompiledPersonaFields
  value: number
  reason: string
}

const clamp = (value: number, low: number, high: number) => Math.max(low, Math.min(high, value))
const round3 = (v: number) => Math.round(v * 1000) / 1000
const round1 = (v: number) => Math.round(v * 10) / 10

export function inferTemperament(dims: Partial<PersonaDimensions>): {
  fields: CompiledPersonaFields
  inferences: Inference[]
} {
  const d = { ...DEFAULT_DIMENSIONS, ...dims }
  const warmth = clamp(d.warmth, -1.0, 1.0)
  const energy = clamp(d.energy, 0.0, 1.0)
  const assertiveness = clamp(d.assertiveness, 0.0, 1.0)
  const volatility = clamp(d.volatility, 0.0, 1.0)
  const resilience = clamp(d.resilience, 0.0, 1.0)
  const opinionFirmness = clamp(d.opinionFirmness, 0.0, 1.0)
  const opennessToTrust = clamp(d.opennessToTrust, 0.0, 1.0)
  const warmthGrowth = clamp(d.warmthGrowth, 0.0, 1.0)
  const emotionalLingering = clamp(d.emotionalLingering, 0.0, 1.0)

  const inferences: Inference[] = []
  const set = (field: keyof CompiledPersonaFields, value: number, dimensionName: string, score: number, note: string) => {
    inferences.push({ field, value, reason: `${dimensionName}=${score.toFixed(2)} -> ${note}` })
    return value
  }

  const fields: CompiledPersonaFields = {
    baselineValence: set(
      "baselineValence",
      round3(warmth * 0.6),
      "warmth",
      warmth,
      "how warm vs. cold the description reads, scaled into the ±0.6 valence bound (a friend can never be pinned fully positive)",
    ),
    baselineArousal: set(
      "baselineArousal",
      round3(0.15 + energy * 0.7),
      "energy",
      energy,
      "calm/low-key (0) to excitable/high-energy (1), scaled into the 0.15-0.85 bound",
    ),
    baselineDominance: set(
      "baselineDominance",
      round3(0.15 + assertiveness * 0.7),
      "assertiveness",
      assertiveness,
      "yielding (0) to take-charge (1), scaled into the 0.15-0.85 bound",
    ),
    valenceDriftRate: set(
      "valenceDriftRate",
      round3(0.1 + volatility * 0.6),
      "volatility",
      volatility,
      "how much mood swings drives how fast valence itself moves",
    ),
    arousalResponseRate: set(
      "arousalResponseRate",
      round3(0.15 + volatility * 0.65),
      "volatility",
      volatility,
      "a more reactive temperament also means arousal responds to events faster",
    ),
    dominanceStability: set(
      "dominanceStability",
      round3(0.05 + opinionFirmness * 0.7),
      "opinion_firmness",
      opinionFirmness,
      "easily swayed (0) to stubborn/consistent (1)",
    ),
    trustChangeRate: set(
      "trustChangeRate",
      round3(0.05 + opennessToTrust * 0.4),
      "openness_to_trust",
      opennessToTrust,
      "guarded (0) to quick-to-trust (1) shapes how fast trust itself can move",
    ),
    attachmentGrowthRate: set(
      "attachmentGrowthRate",
      round3(0.02 + warmthGrowth * 0.25),
      "warmth_growth",
      warmthGrowth,
      "standoffish long-term (0) to quickly-attached (1)",
    ),
    moodDecayRate: set(
      "moodDecayRate",
      round3(0.02 + resilience * 0.4),
      "resilience",
      resilience,
      "dwells on things (0) to bounces back quickly (1) -- higher means faster return to baseline mood",
    ),
    dopamineHalflifeS: set(
      "dopamineHalflifeS",
      round1(30 + emotionalLingering * 300),
      "emotional_lingering",
      emotionalLingering,
      "how long a good moment's glow lasts, in seconds",
    ),
    cortisolHalflifeS: set(
      "cortisolHalflifeS",
      round1(200 + emotionalLingering * 1000),
      "emotional_lingering",
      emotionalLingering,
      "how long a bad moment's sting lingers, in seconds -- longer than dopamine's by construction",
    ),
    adrenalineHalflifeS: set(
      "adrenalineHalflifeS",
      round1(100 + emotionalLingering * 500),
      "emotional_lingering",
      emotionalLingering,
      "how long a startle/interruption/shock reaction lingers -- sits between dopamine's and cortisol's by construction",
    ),
    initialTrust: set(
      "initialTrust",
      round3(0.2 + opennessToTrust * 0.6),
      "openness_to_trust",
      opennessToTrust,
      "where the relationship's trust starts (never at the extremes)",
    ),
    initialAttachment: set(
      "initialAttachment",
      round3(0.05 + warmthGrowth * 0.35),
      "warmth_growth",
      warmthGrowth,
      "where attachment starts -- deliberately low; attachment is meant to be earned",
    ),
  }

  return { fields, inferences }
}
