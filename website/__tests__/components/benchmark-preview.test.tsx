import React from 'react'
import { render, screen } from '@testing-library/react'
import { expect, test, describe } from 'vitest'
import { BenchmarkPreview } from '@/components/benchmark-preview'

describe('BenchmarkPreview', () => {
  test('renders without crashing and displays hardware matrix text', () => {
    render(<BenchmarkPreview />)
    expect(screen.getByText(/Hardware Matrix & Latency Waterfalls/i)).toBeInTheDocument()
    expect(screen.getByText(/Google Colab/i)).toBeInTheDocument()
  })
})
