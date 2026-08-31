import { expect, test, describe } from 'vitest'
import { CHANGELOG_DATA } from '@/lib/changelog-data'

describe('changelog-data', () => {
  test('CHANGELOG_DATA is a non-empty array with expected structure', () => {
    expect(Array.isArray(CHANGELOG_DATA)).toBe(true)
    expect(CHANGELOG_DATA.length).toBeGreaterThan(0)

    CHANGELOG_DATA.forEach(entry => {
      expect(entry).toHaveProperty('version')
      expect(typeof entry.version).toBe('string')
      expect(entry).toHaveProperty('date')
      expect(entry).toHaveProperty('highlights')
      expect(Array.isArray(entry.highlights)).toBe(true)
    })
  })
})
