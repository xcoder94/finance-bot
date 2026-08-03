import { describe, expect, it } from 'vitest'

import { CHART_CATEGORY_COLORS } from './chartColors'
import {
  buildAnalyticsHistoryFetchKey,
  getAnalyticsHistoryExpenseCategoryId,
} from './analyticsHistoryTab'

describe('buildAnalyticsHistoryFetchKey', () => {
  it('includes range and category id without charts currency', () => {
    const filter = {
      id: 'sub-groceries',
      name: 'Продукты',
      color: CHART_CATEGORY_COLORS[0],
    }
    const rangeKey = '2026-08-01|2026-08-31'
    const chartsFetchKey = `${rangeKey}|UZS`

    expect(buildAnalyticsHistoryFetchKey(rangeKey, filter)).toBe(
      '2026-08-01|2026-08-31|sub-groceries',
    )
    expect(buildAnalyticsHistoryFetchKey(rangeKey, null)).toBe('2026-08-01|2026-08-31|')
    expect(buildAnalyticsHistoryFetchKey(rangeKey, null)).not.toBe(chartsFetchKey)
  })
})

describe('getAnalyticsHistoryExpenseCategoryId', () => {
  it('returns category id when filter is set', () => {
    expect(
      getAnalyticsHistoryExpenseCategoryId({
        id: 'sub-groceries',
        name: 'Продукты',
        color: CHART_CATEGORY_COLORS[0],
      }),
    ).toBe('sub-groceries')
  })

  it('returns undefined when filter is cleared', () => {
    expect(getAnalyticsHistoryExpenseCategoryId(null)).toBeUndefined()
  })
})
