import { createContext, useContext, type ReactNode } from 'react'

import type { HistoryCategoryFilter } from '../utils/analyticsDrill'
import type { AnalyticsTab, DrillParent } from '../utils/analyticsTabState'
import type { Currency } from '../utils/formatCurrency'
import type { PeriodTab, ResolvedRange, SelectedMonth } from '../utils/periodFilter'

export type AnalyticsContextValue = {
  activeTab: AnalyticsTab
  setActiveTab: (tab: AnalyticsTab) => void
  drillParent: DrillParent | null
  setDrillParent: (parent: DrillParent | null) => void
  historyCategoryFilter: HistoryCategoryFilter | null
  setHistoryCategoryFilter: (filter: HistoryCategoryFilter | null) => void
  periodTab: PeriodTab
  setPeriodTab: (tab: PeriodTab) => void
  selectedMonth: SelectedMonth
  setSelectedMonth: (month: SelectedMonth) => void
  rangeFrom: string
  setRangeFrom: (value: string) => void
  rangeTo: string
  setRangeTo: (value: string) => void
  rangeFromTouched: boolean
  setRangeFromTouched: (value: boolean) => void
  rangeToTouched: boolean
  setRangeToTouched: (value: boolean) => void
  currency: Currency
  setCurrency: (currency: Currency) => void
  range: ResolvedRange | null
  rangeOrderInvalid: boolean
  rangeFetchEnabled: boolean
  rangeKey: string
  fetchKey: string
}

const AnalyticsContext = createContext<AnalyticsContextValue | null>(null)

export function AnalyticsProvider({
  value,
  children,
}: {
  value: AnalyticsContextValue
  children: ReactNode
}) {
  return <AnalyticsContext.Provider value={value}>{children}</AnalyticsContext.Provider>
}

export function useAnalyticsContext(): AnalyticsContextValue {
  const context = useContext(AnalyticsContext)
  if (!context) {
    throw new Error('useAnalyticsContext must be used within AnalyticsProvider')
  }
  return context
}
