// Port of MemoryStore._base_activation and _spacing_hours
// (backend/app/state/memory_store.py:718-778). Same formula shared by every
// retrieval-scoring path in the real system (Qdrant, SQLite, and Postgres
// branches all call this).

// Constants from backend/app/state/memory_store.py:123-133 and
// Config.ACTR_DECAY_RATE's default (backend/app/config.py:299).
export const ACTR_DECAY_RATE_DEFAULT = 0.5
export const ACTR_IMPORTANCE_WEIGHT = 1.5
export const ACTR_EMO_PROXIMITY_WEIGHT = 0.15
export const ACTR_SPACING_WEIGHT = 0.15

export interface ActivationInputs {
  recallCount: number
  hoursSince: number
  importanceScore: number
  /** Emotional distance in [0, 1]; 0 = identical valence to current state. */
  distEmo: number
  /** Average hours between recalls, or null if fewer than 2 recalls. */
  spacingHours: number | null
  decayRate?: number
}

// ACT-R base-level activation: ln(freq) - d*ln(recency) plus importance,
// emotional-proximity, and spacing terms.
export function baseActivation(inputs: ActivationInputs): number {
  const decayRate = inputs.decayRate ?? ACTR_DECAY_RATE_DEFAULT
  const spacingBonus =
    inputs.spacingHours !== null ? ACTR_SPACING_WEIGHT * Math.log(inputs.spacingHours + 1.0) : 0.0

  return (
    Math.log(Math.max(inputs.recallCount, 1)) -
    decayRate * Math.log(inputs.hoursSince + 1.0) +
    ACTR_IMPORTANCE_WEIGHT * inputs.importanceScore +
    ACTR_EMO_PROXIMITY_WEIGHT * (1.0 - inputs.distEmo) +
    spacingBonus
  )
}

// Approximate average gap between recalls, in hours -- spreads the span from
// creation to the most recent recall evenly across recallCount recalls. An
// approximation of the true ACT-R spacing sum, not the literal formula (see
// the Python docstring for why: only recall_count + last_recalled_at are
// persisted, not a timestamp per individual past recall).
export function spacingHours(
  recallCount: number,
  createdAtMs: number | null,
  lastRecallMs: number | null,
): number | null {
  if (recallCount < 2 || createdAtMs === null || lastRecallMs === null) return null
  const spanHours = (lastRecallMs - createdAtMs) / (1000 * 3600)
  if (spanHours <= 0.0) return null
  return spanHours / recallCount
}

// Simplified single-hop spreading-activation boost, illustrating the
// Personalized-PageRank-style graph boost (backend/app/state/memory_store.py's
// _apply_ppr_spreading_activation, Rust-accelerated in the real system). This
// is NOT a literal port of that iterative PPR implementation -- it's a
// one-hop approximation for the visualizer: a queried node distributes a
// fraction of its own activation to its direct neighbors, split by degree.
export function singleHopSpreadBoost(
  queriedActivation: number,
  neighborCount: number,
  dampingFactor = 0.85,
): number {
  if (neighborCount <= 0) return 0
  return (dampingFactor * queriedActivation) / neighborCount
}
