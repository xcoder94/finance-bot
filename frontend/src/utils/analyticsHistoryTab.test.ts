import { describe, expect, it } from 'vitest'

import { historyFilterForUncategorized } from './analyticsDrill'
import { historyFilterAfterTabSwitch } from './analyticsTabState'
import { CHART_CATEGORY_COLORS } from './chartColors'
import {
  buildAnalyticsHistoryFetchKey,
  filterHistoryByCurrency,
  getAnalyticsHistoryExpenseCategoryId,
  isAnalyticsHistoryUncategorized,
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

describe('uncategorized filter', () => {
  const filter = historyFilterForUncategorized('Без категории')

  it('has no category id, flags uncategorized, own fetch key', () => {
    expect(getAnalyticsHistoryExpenseCategoryId(filter)).toBeUndefined()
    expect(isAnalyticsHistoryUncategorized(filter)).toBe(true)
    expect(isAnalyticsHistoryUncategorized(null)).toBe(false)
    expect(buildAnalyticsHistoryFetchKey('r', filter)).toBe('r|uncategorized')
  })

  it('survives switching to history tab and is cleared on charts', () => {
    expect(historyFilterAfterTabSwitch(filter, 'history')).toBe(filter)
    expect(historyFilterAfterTabSwitch(filter, 'charts')).toBeNull()
  })
})

describe('filterHistoryByCurrency (B17)', () => {
  it('keeps only rows of the selected currency', () => {
    const rows = [{ currency: 'UZS' }, { currency: 'USD' }, { currency: 'UZS' }]
    expect(filterHistoryByCurrency(rows, 'UZS')).toHaveLength(2)
    expect(filterHistoryByCurrency(rows, 'USD')).toHaveLength(1)
  })
})
