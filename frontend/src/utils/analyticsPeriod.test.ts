import { describe, expect, it } from 'vitest'

import * as analyticsPeriod from './analyticsPeriod'
import { twelveMonthKeysEndingAt } from './analyticsPeriod'

describe('twelveMonthKeysEndingAt', () => {
  it('returns 12 month keys ending at the selected month', () => {
    expect(twelveMonthKeysEndingAt({ year: 2026, month: 8 })).toEqual([
      '2025-09',
      '2025-10',
      '2025-11',
      '2025-12',
      '2026-01',
      '2026-02',
      '2026-03',
      '2026-04',
      '2026-05',
      '2026-06',
      '2026-07',
      '2026-08',
    ])
  })

  it('handles year boundary when selected month is January', () => {
    expect(twelveMonthKeysEndingAt({ year: 2026, month: 1 })).toEqual([
      '2025-02',
      '2025-03',
      '2025-04',
      '2025-05',
      '2025-06',
      '2025-07',
      '2025-08',
      '2025-09',
      '2025-10',
      '2025-11',
      '2025-12',
      '2026-01',
    ])
  })

  it('does not expose an FX conversion helper', () => {
    expect('convertUzsToUsd' in analyticsPeriod).toBe(false)
  })
})
