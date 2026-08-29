import { expect, test, describe } from 'vitest'
import { PRESSURE_SCENARIOS, HARDWARE_MATRIX, LATENCY_WATERFALL, CONTAINER_FOOTPRINTS, REAL_MICRO_BENCHMARKS } from '@/lib/benchmark-data'

describe('benchmark-data', () => {
  test('PRESSURE_SCENARIOS has 9 items', () => {
    expect(PRESSURE_SCENARIOS).toHaveLength(9)
  })
  
  test('HARDWARE_MATRIX is non-empty with expected fields', () => {
    expect(HARDWARE_MATRIX.length).toBeGreaterThan(0)
    expect(HARDWARE_MATRIX[0]).toHaveProperty('platform')
    expect(HARDWARE_MATRIX[0]).toHaveProperty('ttftMs')
  })

  test('LATENCY_WATERFALL steps sum correctly', () => {
    const sum = LATENCY_WATERFALL.reduce((acc, curr) => acc + curr.latencyMs, 0)
    expect(sum).toBeGreaterThan(0)
  })

  test('CONTAINER_FOOTPRINTS entries have service and memoryMiB fields', () => {
    CONTAINER_FOOTPRINTS.forEach(entry => {
      expect(entry).toHaveProperty('service')
      expect(entry).toHaveProperty('memoryMiB')
    })
  })

  test('REAL_MICRO_BENCHMARKS has expected shape', () => {
    expect(REAL_MICRO_BENCHMARKS.length).toBeGreaterThan(0)
    expect(REAL_MICRO_BENCHMARKS[0]).toHaveProperty('measurementId')
  })
})
