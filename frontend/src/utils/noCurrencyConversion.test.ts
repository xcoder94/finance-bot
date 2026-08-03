import { describe, expect, it } from 'vitest'

import type { TrendEntry } from '../api/analytics'
import * as analyticsCharts from './analyticsCharts'
import {
  assertNoFxConversionUsed,
  filterEntriesByCurrency,
  sumExpenseByCurrency,
} from './noCurrencyConversion'

const trendEntries: TrendEntry[] = [
  { month: '2026-08', currency: 'UZS', income: 1_000_000, expense: 500_000 },
  { month: '2026-08', currency: 'USD', income: 100, expense: 50 },
]

describe('assertNoFxConversionUsed', () => {
  it('documents that charts must not use FX conversion helpers', () => {
    expect(assertNoFxConversionUsed).toBe(false)
  })
})

describe('filterEntriesByCurrency', () => {
  it('filters by currency without transforming amounts', () => {
    const usdEntries = filterEntriesByCurrency(trendEntries, 'USD')
    expect(usdEntries).toEqual([
      { month: '2026-08', currency: 'USD', income: 100, expense: 50 },
    ])
  })
})

describe('sumExpenseByCurrency', () => {
  it('sums raw wallet amounts for the selected currency', () => {
    expect(sumExpenseByCurrency(trendEntries, 'USD')).toBe(50)
    expect(sumExpenseByCurrency(trendEntries, 'UZS')).toBe(500_000)
  })
})

describe('charts path', () => {
  it('does not expose convertUzsToUsd', () => {
    expect('convertUzsToUsd' in analyticsCharts).toBe(false)
  })

  it('buildTrendChartRows keeps USD amounts unchanged', () => {
    const rows = analyticsCharts.buildTrendChartRows(
      trendEntries,
      'USD',
      ['2026-08'],
      (monthKey) => monthKey,
    )
    expect(rows).toEqual([
      { month: '2026-08', label: '2026-08', income: 100, expense: 50 },
    ])
  })
})
