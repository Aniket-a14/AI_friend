import { expect, test, describe } from 'vitest'
import { inferTemperament, DEFAULT_DIMENSIONS } from '@/lib/persona-compiler-math'

describe('persona-compiler-math (backend/app/persona/compiler.py::_infer_temperament port)', () => {
  test('default dimensions produce the documented midpoint defaults', () => {
    const { fields } = inferTemperament({})
    // warmth=0.0 -> baseline_valence = 0.0
    expect(fields.baselineValence).toBeCloseTo(0.0, 6)
    // energy=0.5 -> 0.15 + 0.5*0.70 = 0.5
    expect(fields.baselineArousal).toBeCloseTo(0.5, 6)
    // assertiveness=0.5 -> 0.15 + 0.5*0.70 = 0.5
    expect(fields.baselineDominance).toBeCloseTo(0.5, 6)
  })

  test('warmth=1.0 (maximally warm) hits the +0.6 valence bound exactly', () => {
    const { fields } = inferTemperament({ ...DEFAULT_DIMENSIONS, warmth: 1.0 })
    expect(fields.baselineValence).toBeCloseTo(0.6, 6)
  })

  test('warmth=-1.0 (maximally cold) hits the -0.6 valence bound exactly', () => {
    const { fields } = inferTemperament({ ...DEFAULT_DIMENSIONS, warmth: -1.0 })
    expect(fields.baselineValence).toBeCloseTo(-0.6, 6)
  })

  test('half-life ordering is preserved by construction at every emotional_lingering value', () => {
    for (const lingering of [0.0, 0.25, 0.5, 0.75, 1.0]) {
      const { fields } = inferTemperament({ ...DEFAULT_DIMENSIONS, emotionalLingering: lingering })
      expect(fields.dopamineHalflifeS).toBeLessThan(fields.adrenalineHalflifeS)
      expect(fields.adrenalineHalflifeS).toBeLessThan(fields.cortisolHalflifeS)
    }
  })

  test('emotional_lingering=0.5 matches the documented default half-lives', () => {
    const { fields } = inferTemperament({ ...DEFAULT_DIMENSIONS, emotionalLingering: 0.5 })
    // 30 + 0.5*300 = 180... but the real deployment default is 90s, computed
    // from a description-derived score, not this midpoint -- this test only
    // checks the *formula*, not that 0.5 reproduces the deployment default.
    expect(fields.dopamineHalflifeS).toBeCloseTo(30 + 0.5 * 300, 6)
    expect(fields.cortisolHalflifeS).toBeCloseTo(200 + 0.5 * 1000, 6)
    expect(fields.adrenalineHalflifeS).toBeCloseTo(100 + 0.5 * 500, 6)
  })

  test('values are clamped to each dimension bound before scoring', () => {
    const { fields } = inferTemperament({ warmth: 5.0, energy: -2.0 })
    expect(fields.baselineValence).toBeCloseTo(0.6, 6) // warmth clamped to 1.0
    expect(fields.baselineArousal).toBeCloseTo(0.15, 6) // energy clamped to 0.0
  })

  test('inferences array has one entry per output field with a human-readable reason', () => {
    const { fields, inferences } = inferTemperament({})
    expect(inferences).toHaveLength(Object.keys(fields).length)
    for (const inf of inferences) {
      expect(inf.reason).toMatch(/=.*->/)
    }
  })
})
