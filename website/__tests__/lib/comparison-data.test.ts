import { expect, test, describe } from 'vitest'
import { COMPARISON_DATA } from '@/lib/comparison-data'

describe('comparison-data', () => {
  test('COMPARISON_DATA matrix structure and AI Friend presence', () => {
    expect(COMPARISON_DATA.length).toBeGreaterThan(0)

    COMPARISON_DATA.forEach(row => {
      expect(row).toHaveProperty('dimension')
      expect(row).toHaveProperty('aiFriend')
      expect(row).toHaveProperty('characterAi')
      expect(row).toHaveProperty('openAiRealtime')
      expect(row).toHaveProperty('humeEvi')
      expect(row).toHaveProperty('elevenLabsAgents')
      expect(row).toHaveProperty('category')
    })
  })
})
