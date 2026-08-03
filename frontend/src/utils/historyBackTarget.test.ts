import { describe, expect, it } from 'vitest'

import { historyBackTarget } from './historyBackTarget'

describe('historyBackTarget', () => {
  it('returns home when opened from Home', () => {
    expect(historyBackTarget({ from: 'home' })).toBe('/')
  })

  it('returns null without home origin state', () => {
    expect(historyBackTarget(null)).toBeNull()
    expect(historyBackTarget(undefined)).toBeNull()
    expect(historyBackTarget({})).toBeNull()
    expect(historyBackTarget({ from: 'analytics' })).toBeNull()
  })
})
