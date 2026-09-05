// Exact 1:1 port of AgentState.update_from_appraisal's PAD + relational update
// (backend/app/state/agent_state.py:1301-1372). ALMA mood-pull for PAD, Marsh
// (1994) trust for the three trust components, Bowlby attachment scaled by
// interaction frequency.

export interface AppraisalDims {
  /** Goal congruence */
  G: number
  /** Relationship impact */
  RI: number
  /** Novelty */
  N: number
  /** Relevance */
  R: number
  /** Agency */
  A: number
  /** Norm alignment */
  NA: number
}

export interface RelationalState {
  mood: number
  energy: number
  dominance: number
  trustBenevolence: number
  trustCompetence: number
  trustIntegrity: number
  attachment: number
  interactionCount: number
}

export interface RelationalCoefficients {
  /** alpha: valence_drift_rate */
  alpha: number
  /** beta: arousal_response_rate */
  beta: number
  /** gamma: dominance_stability */
  gamma: number
  /** delta: trust_change_rate (Marsh) */
  delta: number
  /** epsilon: attachment_growth_rate (Bowlby) */
  epsilon: number
}

const clamp01 = (v: number) => Math.max(0.0, Math.min(1.0, v))

export function trustOf(state: RelationalState): number {
  return (state.trustBenevolence + state.trustCompetence + state.trustIntegrity) / 3
}

const DEFAULT_WEIGHTS = { w1: 0.6, w2: 0.4, w3: 0.6, w4: 0.4, w5: 0.6, w6: 0.4 }

export function updateFromAppraisal(
  state: RelationalState,
  appraisal: AppraisalDims,
  coefficients: RelationalCoefficients,
  weights: Partial<typeof DEFAULT_WEIGHTS> = {},
): RelationalState {
  const { w1, w2, w3, w4, w5, w6 } = { ...DEFAULT_WEIGHTS, ...weights }
  const { G, RI, N, R, A, NA } = appraisal
  const { alpha, beta, gamma, delta, epsilon } = coefficients

  const mood = (1 - alpha) * state.mood + alpha * (w1 * G + w2 * RI)
  const energy = (1 - beta) * state.energy + beta * (w3 * N + w4 * R)
  const dominance = (1 - gamma) * state.dominance + gamma * (w5 * A + w6 * NA)

  const trustBenevolence = clamp01(state.trustBenevolence + delta * RI)
  const trustCompetence = clamp01(state.trustCompetence + delta * (0.6 * G + 0.4 * R))
  const trustIntegrity = clamp01(state.trustIntegrity + delta * NA)

  const interactionCount = state.interactionCount + 1
  const freq = Math.min(1.0, interactionCount / 100.0)
  const trust = (trustBenevolence + trustCompetence + trustIntegrity) / 3
  const attachment = clamp01(state.attachment + epsilon * trust * freq)

  return {
    mood,
    energy,
    dominance,
    trustBenevolence,
    trustCompetence,
    trustIntegrity,
    attachment,
    interactionCount,
  }
}

export function initialRelationalState(): RelationalState {
  return {
    mood: 0,
    energy: 0.5,
    dominance: 0.5,
    trustBenevolence: 0.5,
    trustCompetence: 0.5,
    trustIntegrity: 0.5,
    attachment: 0.1,
    interactionCount: 0,
  }
}
