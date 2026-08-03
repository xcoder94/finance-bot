import { describe, expect, it } from 'vitest'

import * as analyticsChartsTabModule from './analyticsChartsTab'
import {
  elapsedDaysInPeriod,
  extendCategoryColorMap,
  formatChartsEmptyMonth,
  isChartsTabEmpty,
  mergeCategoryIds,
} from './analyticsChartsTab'
import { assertNoFxConversionUsed } from './noCurrencyConversion'
import { twelveMonthKeysEndingAt } from './analyticsPeriod'

describe('mergeCategoryIds', () => {
  it('keeps active order and appends analytics-only ids', () => {
    expect(mergeCategoryIds(['parent-1', 'parent-2'], ['deleted-parent'])).toEqual([
      'parent-1',
      'parent-2',
      'deleted-parent',
    ])
  })
})

describe('extendCategoryColorMap', () => {
  it('assigns colors to analytics-only category ids', () => {
    const colorMap = extendCategoryColorMap(['parent-1'], ['deleted-parent'])
    expect(colorMap.get('deleted-parent')).toBeGreaterThanOrEqual(1)
    expect(colorMap.get('deleted-parent')).toBeLessThanOrEqual(8)
  })
})

describe('isChartsTabEmpty', () => {
  it('is true when there is no expense total and no slices', () => {
    expect(isChartsTabEmpty(0, 0)).toBe(true)
  })

  it('is false when expense total is positive', () => {
    expect(isChartsTabEmpty(100, 0)).toBe(false)
  })

  it('is false when slices exist', () => {
    expect(isChartsTabEmpty(0, 2)).toBe(false)
  })
})

describe('elapsedDaysInPeriod', () => {
  it('counts through Tashkent today for the current month', () => {
    const now = new Date('2026-08-15T12:00:00.000Z')
    expect(
      elapsedDaysInPeriod(
        '2026-08-01T00:00:00.000+05:00',
        '2026-08-31T23:59:59.999+05:00',
        now,
      ),
    ).toBe(15)
  })

  it('uses the full period for a finished month', () => {
    const now = new Date('2026-08-15T12:00:00.000Z')
    expect(
      elapsedDaysInPeriod(
        '2026-07-01T00:00:00.000+05:00',
        '2026-07-31T23:59:59.999+05:00',
        now,
      ),
    ).toBe(31)
  })
})

describe('formatChartsEmptyMonth', () => {
  it('returns lowercase Russian month name', () => {
    expect(formatChartsEmptyMonth({ year: 2026, month: 8 })).toBe('август')
  })
})

describe('charts tab module', () => {
  it('does not expose FX conversion helpers', () => {
    expect(assertNoFxConversionUsed).toBe(false)
    expect('convertUzsToUsd' in analyticsChartsTabModule).toBe(false)
  })

  it('uses twelveMonthKeysEndingAt for trend window', () => {
    expect(twelveMonthKeysEndingAt({ year: 2026, month: 3 })).toEqual([
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
      '2026-02',
      '2026-03',
    ])
  })
})
