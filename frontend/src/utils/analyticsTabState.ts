import type { HistoryCategoryFilter } from './analyticsDrill'
import type { Currency } from './formatCurrency'
import type { PeriodTab, SelectedMonth } from './periodFilter'

export type AnalyticsTab = 'charts' | 'history'

export type DrillParent = {
  id: string
  name: string
}

export type AnalyticsShellState = {
  activeTab: AnalyticsTab
  periodTab: PeriodTab
  selectedMonth: SelectedMonth
  rangeFrom: string
  rangeTo: string
  rangeFromTouched: boolean
  rangeToTouched: boolean
  currency: Currency
  drillParent: DrillParent | null
  historyCategoryFilter: HistoryCategoryFilter | null
}

export function switchAnalyticsTab(
  state: AnalyticsShellState,
  tab: AnalyticsTab,
): AnalyticsShellState {
  return {
    ...state,
    activeTab: tab,
  }
}

export function applyAnalyticsCurrencyChange(
  state: AnalyticsShellState,
  currency: Currency,
): AnalyticsShellState {
  return {
    ...state,
    currency,
  }
}
