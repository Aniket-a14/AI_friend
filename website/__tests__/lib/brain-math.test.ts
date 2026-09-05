import { expect, test, describe } from 'vitest'
import {
  newDomainCalibration,
  recordObservation,
  calibrate,
  evaluateDirective,
} from '@/lib/brain-math/calibration'
import { updateKnownConcepts, extractBeliefDiscrepancies, MAX_KNOWN_CONCEPTS } from '@/lib/brain-math/theory-of-mind'
import { updateFromAppraisal, initialRelationalState, trustOf } from '@/lib/brain-math/trust-attachment'
import { baseActivation, spacingHours, singleHopSpreadBoost } from '@/lib/brain-math/memory-activation'

describe('calibration (backend/app/cognitive/calibration.py port)', () => {
  test('record_observation matches hand-computed Brier score', () => {
    // Python: c = DomainCalibration(domain="x"); c.record_observation(0.9, 1)
    // squared_error = (0.9-1)**2 = 0.01; brier = (0*0 + 0.01)/1 = 0.01
    let c = newDomainCalibration('x')
    c = recordObservation(c, 0.9, 1)
    expect(c.brierScore).toBeCloseTo(0.01, 6)
    expect(c.sampleCount).toBe(1)

    // second observation: predicted=0.2, actual=0 -> squared_error=0.04
    // brier = (0.01*1 + 0.04)/2 = 0.025
    c = recordObservation(c, 0.2, 0)
    expect(c.brierScore).toBeCloseTo(0.025, 6)
    expect(c.sampleCount).toBe(2)
  })

  test('calibrate discounts confidence by half the Brier score', () => {
    const c = { domain: 'x', sampleCount: 1, brierScore: 0.2 }
    // 0.8 * (1 - 0.5*0.2) = 0.8 * 0.9 = 0.72
    expect(calibrate(c, 0.8)).toBeCloseTo(0.72, 6)
  })

  test('evaluate_directive thresholds match the Python cutoffs exactly', () => {
    expect(evaluateDirective([], {}, 'x', 0.75).directive).toBe('PROCEED')
    expect(evaluateDirective([], {}, 'x', 0.74).directive).toBe('HEDGE')
    expect(evaluateDirective([], {}, 'x', 0.5).directive).toBe('HEDGE')
    expect(evaluateDirective([], {}, 'x', 0.49).directive).toBe('ASK_CLARIFICATION')
    expect(evaluateDirective([], {}, 'x', 0.3).directive).toBe('ASK_CLARIFICATION')
    expect(evaluateDirective([], {}, 'x', 0.29).directive).toBe('VERIFY')
  })

  test('known limitation short-circuits to ABSTAIN with zero confidence', () => {
    const result = evaluateDirective(['medical diagnosis'], {}, 'x', 0.95, 'give me a medical diagnosis please')
    expect(result.directive).toBe('ABSTAIN')
    expect(result.calibrated).toBe(0.0)
  })
})

describe('theory-of-mind (backend/app/cognitive/tom.py port)', () => {
  test('update_known_concepts adds new words, dedupes case-insensitively, skips stop words', () => {
    const result = updateKnownConcepts([], 'I really love hiking and photography, hiking is great')
    // "really" is a stop word; "hiking" appears twice but only tracked once
    expect(result).toContain('love')
    expect(result).toContain('hiking')
    expect(result).toContain('photography')
    expect(result).not.toContain('really')
    expect(result.filter((w) => w.toLowerCase() === 'hiking')).toHaveLength(1)
  })

  test('sliding window caps at MAX_KNOWN_CONCEPTS and keeps the most recent', () => {
    const many = Array.from({ length: MAX_KNOWN_CONCEPTS + 10 }, (_, i) => `wordnum${i}`)
    const result = updateKnownConcepts(many, 'brandnewword')
    expect(result).toHaveLength(MAX_KNOWN_CONCEPTS)
    expect(result[result.length - 1]).toBe('brandnewword')
    expect(result).not.toContain('wordnum0')
  })

  test('extract_belief_discrepancies flags only mismatched, case-insensitive-safe beliefs', () => {
    const discrepancies = extractBeliefDiscrepancies(
      { capital: 'Sydney', population: '20 million' },
      { capital: 'Canberra', population: '20 MILLION' },
    )
    expect(Object.keys(discrepancies)).toEqual(['capital'])
    expect(discrepancies.capital).toEqual({ userBelief: 'Sydney', groundTruth: 'Canberra' })
  })
})

describe('trust-attachment (backend/app/state/agent_state.py port)', () => {
  test('update_from_appraisal matches hand-computed values for one turn', () => {
    const state = initialRelationalState()
    const coefficients = { alpha: 0.1, beta: 0.15, gamma: 0.1, delta: 0.05, epsilon: 0.03 }
    const appraisal = { G: 0.8, RI: 0.5, N: 0.2, R: 0.6, A: 0.4, NA: 0.9 }

    const next = updateFromAppraisal(state, appraisal, coefficients)

    // mood = (1-0.1)*0 + 0.1*(0.6*0.8 + 0.4*0.5) = 0.1*(0.48+0.2) = 0.1*0.68 = 0.068
    expect(next.mood).toBeCloseTo(0.068, 6)
    // energy = (1-0.15)*0.5 + 0.15*(0.6*0.2 + 0.4*0.6) = 0.425 + 0.15*0.36 = 0.425+0.054=0.479
    expect(next.energy).toBeCloseTo(0.479, 6)
    // dominance = (1-0.1)*0.5 + 0.1*(0.6*0.4+0.4*0.9) = 0.45 + 0.1*0.6 = 0.45+0.06=0.51
    expect(next.dominance).toBeCloseTo(0.51, 6)
    // trust_benevolence = 0.5 + 0.05*0.5 = 0.525
    expect(next.trustBenevolence).toBeCloseTo(0.525, 6)
    // trust_competence = 0.5 + 0.05*(0.6*0.8+0.4*0.6) = 0.5+0.05*0.72=0.536
    expect(next.trustCompetence).toBeCloseTo(0.536, 6)
    // trust_integrity = 0.5 + 0.05*0.9 = 0.545
    expect(next.trustIntegrity).toBeCloseTo(0.545, 6)
    expect(next.interactionCount).toBe(1)
    // freq = min(1, 1/100) = 0.01; trust = avg(0.525,0.536,0.545)=0.535333...
    // attachment = 0.1 + 0.03*0.535333*0.01 = 0.1 + 0.00016...
    expect(next.attachment).toBeCloseTo(0.1 + 0.03 * trustOf(next) * 0.01, 6)
  })

  test('trust and attachment stay clamped to [0, 1] under repeated strong updates', () => {
    let state = initialRelationalState()
    const coefficients = { alpha: 0.5, beta: 0.5, gamma: 0.5, delta: 0.9, epsilon: 0.9 }
    const appraisal = { G: 1, RI: 1, N: 1, R: 1, A: 1, NA: 1 }
    for (let i = 0; i < 50; i++) {
      state = updateFromAppraisal(state, appraisal, coefficients)
    }
    expect(state.trustBenevolence).toBeLessThanOrEqual(1.0)
    expect(state.trustCompetence).toBeLessThanOrEqual(1.0)
    expect(state.trustIntegrity).toBeLessThanOrEqual(1.0)
    expect(state.attachment).toBeLessThanOrEqual(1.0)
  })
})

describe('memory-activation (backend/app/state/memory_store.py port)', () => {
  test('base_activation matches hand-computed ACT-R formula', () => {
    // ln(5) - 0.5*ln(25) + 1.5*0.8 + 0.15*(1-0.2), no spacing
    const expected =
      Math.log(5) - 0.5 * Math.log(25) + 1.5 * 0.8 + 0.15 * (1 - 0.2)
    const actual = baseActivation({
      recallCount: 5,
      hoursSince: 24,
      importanceScore: 0.8,
      distEmo: 0.2,
      spacingHours: null,
    })
    expect(actual).toBeCloseTo(expected, 6)
  })

  test('spacing bonus increases activation for spaced vs massed recall at equal frequency/recency', () => {
    const massed = baseActivation({
      recallCount: 4,
      hoursSince: 48,
      importanceScore: 0.5,
      distEmo: 0.5,
      spacingHours: 1, // recalled repeatedly within an hour
    })
    const spaced = baseActivation({
      recallCount: 4,
      hoursSince: 48,
      importanceScore: 0.5,
      distEmo: 0.5,
      spacingHours: 200, // recalled repeatedly, spread over days
    })
    expect(spaced).toBeGreaterThan(massed)
  })

  test('spacing_hours returns null below two recalls or non-positive span, else spreads the span evenly', () => {
    expect(spacingHours(1, 0, 1000)).toBeNull()
    expect(spacingHours(3, 1000, 500)).toBeNull() // negative span
    // 4-hour span (in ms) over 4 recalls = 1 hour average gap
    expect(spacingHours(4, 0, 3_600_000 * 4)).toBeCloseTo(1, 6)
  })

  test('single_hop_spread_boost splits damped activation across neighbors', () => {
    expect(singleHopSpreadBoost(1.0, 4, 0.8)).toBeCloseTo(0.2, 6)
    expect(singleHopSpreadBoost(1.0, 0)).toBe(0)
  })
})
