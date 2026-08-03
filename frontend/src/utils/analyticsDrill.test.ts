import { describe, expect, it } from 'vitest'

import { OTHER_CATEGORY_KEY } from './analyticsConstants'
import { CHART_CATEGORY_COLORS } from './chartColors'
import {
  clearHistoryFilter,
  historyFilterAfterSubcategoryTap,
  isOtherCategoryKey,
  shouldIgnoreDonutTap,
} from './analyticsDrill'

describe('isOtherCategoryKey', () => {
  it('returns true for the overflow key', () => {
    expect(isOtherCategoryKey(OTHER_CATEGORY_KEY)).toBe(true)
  })

  it('returns false for a category id', () => {
    expect(isOtherCategoryKey('cat-food')).toBe(false)
  })
})

describe('shouldIgnoreDonutTap', () => {
  it('ignores taps on the overflow key', () => {
    expect(shouldIgnoreDonutTap(OTHER_CATEGORY_KEY)).toBe(true)
    expect(shouldIgnoreDonutTap('cat-food')).toBe(false)
  })
})

describe('historyFilterAfterSubcategoryTap', () => {
  it('builds a history filter with subcategory id, name and chart color', () => {
    expect(
      historyFilterAfterSubcategoryTap('sub-groceries', 'Продукты', 3),
    ).toEqual({
      id: 'sub-groceries',
      name: 'Продукты',
      color: CHART_CATEGORY_COLORS[2],
    })
  })
})

describe('clearHistoryFilter', () => {
  it('returns null', () => {
    expect(clearHistoryFilter()).toBeNull()
    expect(clearHistoryFilter({ returnToDrill: true })).toBeNull()
  })
})
