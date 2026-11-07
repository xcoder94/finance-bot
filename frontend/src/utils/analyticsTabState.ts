import type { ClearHistoryFilterOptions, HistoryCategoryFilter } from './analyticsDrill'
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
  if (tab === 'charts' && state.historyCategoryFilter !== null) {
    return {
      ...state,
      activeTab: 'charts',
      historyCategoryFilter: null,
    }
  }

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

export function applyClearHistoryFilter(
  state: AnalyticsShellState,
  options?: ClearHistoryFilterOptions,
): AnalyticsShellState {
  const next: AnalyticsShellState = {
    ...state,
    historyCategoryFilter: null,
  }

  if (options?.returnToDrill && state.drillParent) {
    return {
      ...next,
      activeTab: 'charts',
    }
  }

  return next
}

/**
 * Next history filter after a tab switch. Takes the CURRENT filter (use in a functional
 * state updater) so a filter set in the same tick as the switch is not overwritten.
 */
export function historyFilterAfterTabSwitch(
  current: HistoryCategoryFilter | null,
  tab: AnalyticsTab,
): HistoryCategoryFilter | null {
  return tab === 'charts' ? null : current
}
