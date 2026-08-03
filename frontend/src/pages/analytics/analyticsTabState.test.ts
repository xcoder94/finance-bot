import { describe, expect, it } from 'vitest'

import { CHART_CATEGORY_COLORS } from '../../utils/chartColors'
import {
  applyAnalyticsCurrencyChange,
  switchAnalyticsTab,
  type AnalyticsShellState,
} from '../../utils/analyticsTabState'

const baseState: AnalyticsShellState = {
  activeTab: 'charts',
  periodTab: 'month',
  selectedMonth: { year: 2026, month: 8 },
  rangeFrom: '01.08.2026',
  rangeTo: '31.08.2026',
  rangeFromTouched: true,
  rangeToTouched: true,
  currency: 'UZS',
  drillParent: { id: 'parent-food', name: 'Еда' },
  historyCategoryFilter: {
    id: 'sub-groceries',
    name: 'Продукты',
    color: CHART_CATEGORY_COLORS[0],
  },
}

describe('switchAnalyticsTab', () => {
  it('keeps selected month and range when switching tabs', () => {
    const next = switchAnalyticsTab(baseState, 'history')

    expect(next.activeTab).toBe('history')
    expect(next.selectedMonth).toEqual(baseState.selectedMonth)
    expect(next.rangeFrom).toBe(baseState.rangeFrom)
    expect(next.rangeTo).toBe(baseState.rangeTo)
    expect(next.periodTab).toBe(baseState.periodTab)
    expect(next.drillParent).toEqual(baseState.drillParent)
    expect(next.historyCategoryFilter).toEqual(baseState.historyCategoryFilter)
  })
})

describe('applyAnalyticsCurrencyChange', () => {
  it('changes currency without mutating the history filter object', () => {
    const next = applyAnalyticsCurrencyChange(baseState, 'USD')

    expect(next.currency).toBe('USD')
    expect(next.historyCategoryFilter).toBe(baseState.historyCategoryFilter)
    expect(next.historyCategoryFilter).toEqual(baseState.historyCategoryFilter)
    expect(next.selectedMonth).toEqual(baseState.selectedMonth)
    expect(next.rangeFrom).toBe(baseState.rangeFrom)
    expect(next.rangeTo).toBe(baseState.rangeTo)
  })
})
