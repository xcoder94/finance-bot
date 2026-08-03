import { describe, expect, it } from 'vitest'

import { historyBackTarget } from './historyBackTarget'

describe('historyBackTarget', () => {
  it('returns home when opened from Home', () => {
    expect(historyBackTarget({ from: 'home' })).toBe('/')
  })

  it('returns analytics when opened from analytics', () => {
    expect(historyBackTarget({ from: 'analytics' })).toBe('/analytics')
  })

  it('returns null without known origin state', () => {
    expect(historyBackTarget(null)).toBeNull()
    expect(historyBackTarget(undefined)).toBeNull()
    expect(historyBackTarget({})).toBeNull()
  })
})
