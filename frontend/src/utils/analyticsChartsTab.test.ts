import { describe, expect, it } from 'vitest'

import * as analyticsChartsTabModule from './analyticsChartsTab'
import {
  elapsedDaysInPeriod,
  extendCategoryColorMap,
  formatChartsEmptyMonth,
  isChartsTabEmpty,
  mergeCategoryIds,
  uniqueColorIndices,
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

  it('prefers stored color_index from category API', () => {
    const colorMap = extendCategoryColorMap(
      ['parent-1'],
      ['deleted-parent'],
      new Map([
        ['parent-1', 2],
        ['deleted-parent', 6],
      ]),
    )
    expect(colorMap.get('parent-1')).toBe(2)
    expect(colorMap.get('deleted-parent')).toBe(6)
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

describe('uniqueColorIndices (B3 drill-down)', () => {
  it('moves the parent own-spend slice off a colour a child already uses', () => {
    const map = uniqueColorIndices(
      new Map([
        ['child-a', 1],
        ['child-b', 2],
        ['parent', 2],
      ]),
    )
    expect(map.get('child-a')).toBe(1)
    expect(map.get('child-b')).toBe(2)
    expect(map.get('parent')).toBe(3)
    expect(new Set(map.values()).size).toBe(3)
  })
  it('leaves an already distinct map untouched', () => {
    const input = new Map([['a', 4], ['b', 5]])
    expect(uniqueColorIndices(input)).toEqual(input)
  })
})
