import { describe, expect, it } from 'vitest'

import { CHART_CATEGORY_COLORS } from '../../utils/chartColors'
import {
  applyAnalyticsCurrencyChange,
  applyClearHistoryFilter,
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
  it('keeps selected month and range when switching to history', () => {
    const next = switchAnalyticsTab(baseState, 'history')

    expect(next.activeTab).toBe('history')
    expect(next.selectedMonth).toEqual(baseState.selectedMonth)
    expect(next.rangeFrom).toBe(baseState.rangeFrom)
    expect(next.rangeTo).toBe(baseState.rangeTo)
    expect(next.periodTab).toBe(baseState.periodTab)
    expect(next.drillParent).toEqual(baseState.drillParent)
    expect(next.historyCategoryFilter).toEqual(baseState.historyCategoryFilter)
    expect(next.currency).toBe(baseState.currency)
  })

  it('keeps currency when switching between charts and history', () => {
    const usdState: AnalyticsShellState = { ...baseState, currency: 'USD' }

    const history = switchAnalyticsTab(usdState, 'history')
    expect(history.currency).toBe('USD')

    const backToCharts = switchAnalyticsTab(history, 'charts')
    expect(backToCharts.currency).toBe('USD')
  })

  it('clears history filter when switching to charts', () => {
    const historyState: AnalyticsShellState = {
      ...baseState,
      activeTab: 'history',
    }

    const next = switchAnalyticsTab(historyState, 'charts')

    expect(next.activeTab).toBe('charts')
    expect(next.historyCategoryFilter).toBeNull()
    expect(next.drillParent).toEqual(baseState.drillParent)
    expect(next.selectedMonth).toEqual(baseState.selectedMonth)
    expect(next.rangeFrom).toBe(baseState.rangeFrom)
    expect(next.rangeTo).toBe(baseState.rangeTo)
    expect(next.periodTab).toBe(baseState.periodTab)
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

  it('changes currency on history tab without affecting active tab', () => {
    const historyState: AnalyticsShellState = {
      ...baseState,
      activeTab: 'history',
    }

    const next = applyAnalyticsCurrencyChange(historyState, 'USD')

    expect(next.currency).toBe('USD')
    expect(next.activeTab).toBe('history')
    expect(next.historyCategoryFilter).toEqual(baseState.historyCategoryFilter)
  })
})

describe('applyClearHistoryFilter', () => {
  it('clears filter and returns to charts drill while keeping period and drill parent', () => {
    const historyState: AnalyticsShellState = {
      ...baseState,
      activeTab: 'history',
    }

    const next = applyClearHistoryFilter(historyState, { returnToDrill: true })

    expect(next.historyCategoryFilter).toBeNull()
    expect(next.activeTab).toBe('charts')
    expect(next.drillParent).toEqual(baseState.drillParent)
    expect(next.selectedMonth).toEqual(baseState.selectedMonth)
    expect(next.rangeFrom).toBe(baseState.rangeFrom)
    expect(next.rangeTo).toBe(baseState.rangeTo)
    expect(next.periodTab).toBe(baseState.periodTab)
  })

  it('clears filter without changing tab when drill parent is absent', () => {
    const historyState: AnalyticsShellState = {
      ...baseState,
      activeTab: 'history',
      drillParent: null,
    }

    const next = applyClearHistoryFilter(historyState, { returnToDrill: true })

    expect(next.historyCategoryFilter).toBeNull()
    expect(next.activeTab).toBe('history')
  })
})
