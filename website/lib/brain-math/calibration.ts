// Exact 1:1 port of backend/app/cognitive/calibration.py.
// Domain calibration and deterministic metacognitive action directives.

export type MetacognitiveDirective = "PROCEED" | "HEDGE" | "ASK_CLARIFICATION" | "VERIFY" | "ABSTAIN"

export interface DomainCalibration {
  domain: string
  sampleCount: number
  brierScore: number
}

export function newDomainCalibration(domain: string): DomainCalibration {
  return { domain, sampleCount: 0, brierScore: 0.0 }
}

// Update the Brier score from one observed binary outcome.
export function recordObservation(
  calibration: DomainCalibration,
  predictedProb: number,
  actualBinaryOutcome: 0 | 1,
): DomainCalibration {
  const count = calibration.sampleCount
  const squaredError = (predictedProb - actualBinaryOutcome) ** 2
  const brierScore = (calibration.brierScore * count + squaredError) / (count + 1)
  return { ...calibration, brierScore, sampleCount: count + 1 }
}

// Discount raw confidence according to observed Brier error.
export function calibrate(calibration: DomainCalibration, rawConfidence: number): number {
  return rawConfidence * (1.0 - 0.5 * Math.min(1.0, calibration.brierScore))
}

// Return whether a query contains a declared limitation phrase.
export function isKnownLimitation(knownLimitations: string[], query: string): boolean {
  const normalizedQuery = query.toLowerCase()
  return knownLimitations.some((l) => l.trim() && normalizedQuery.includes(l.toLowerCase()))
}

// Choose a deterministic directive from limitations and calibration.
export function evaluateDirective(
  knownLimitations: string[],
  domainCalibrations: Record<string, DomainCalibration>,
  domain: string,
  rawConfidence: number,
  query = "",
): { directive: MetacognitiveDirective; calibrated: number } {
  if (isKnownLimitation(knownLimitations, query)) {
    return { directive: "ABSTAIN", calibrated: 0.0 }
  }

  const domainCalibration = domainCalibrations[domain]
  const calibrated = domainCalibration ? calibrate(domainCalibration, rawConfidence) : rawConfidence

  if (calibrated >= 0.75) return { directive: "PROCEED", calibrated }
  if (calibrated >= 0.5) return { directive: "HEDGE", calibrated }
  if (calibrated >= 0.3) return { directive: "ASK_CLARIFICATION", calibrated }
  return { directive: "VERIFY", calibrated }
}
