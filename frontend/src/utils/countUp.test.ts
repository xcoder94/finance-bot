import { beforeEach, describe, expect, it } from 'vitest'

import { countUpValue, shouldCountUp, resetCountUpPlayed, markCountUpPlayed } from './countUp'

describe('countUpValue', () => {
  it('starts at 0, ends exactly on target, is monotonic', () => {
    expect(countUpValue(1_250_000, 0)).toBe(0)
    expect(countUpValue(1_250_000, 1)).toBe(1_250_000)
    expect(countUpValue(1_250_000, 2)).toBe(1_250_000)
    let prev = -1
    for (let p = 0; p <= 1; p += 0.1) {
      const v = countUpValue(1_250_000, p)
      expect(v).toBeGreaterThanOrEqual(prev)
      prev = v
    }
  })

  it('handles negatives and returns integers', () => {
    expect(countUpValue(-5000, 1)).toBe(-5000)
    expect(Number.isInteger(countUpValue(-5001, 0.37))).toBe(true)
    expect(countUpValue(-5000, 0.5)).toBeLessThan(0)
  })
})

describe('shouldCountUp', () => {
  beforeEach(() => resetCountUpPlayed())

  it('plays once per id', () => {
    expect(shouldCountUp('balance', 100, false)).toBe(true)
    markCountUpPlayed('balance')
    expect(shouldCountUp('balance', 100, false)).toBe(false)
    expect(shouldCountUp('income', 100, false)).toBe(true)
  })

  it('skips zero values and reduced motion', () => {
    expect(shouldCountUp('x', 0, false)).toBe(false)
    expect(shouldCountUp('x', 100, true)).toBe(false)
  })
})
