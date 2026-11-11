import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useNativeBackButtonOverlay } from '../../components/nativeBackButtonContext'
import { PeriodFilterControls } from '../../components/PeriodFilterControls'
import { AnalyticsProvider } from '../../contexts/AnalyticsContext'
import {
  createDefaultAnalyticsShellState,
  useAnalyticsShellStore,
} from '../../store/analyticsShellStore'
import type { HistoryCategoryFilter } from '../../utils/analyticsDrill'
import {
  analyticsBackTarget,
  historyFilterAfterTabSwitch,
  type AnalyticsShellState,
  type AnalyticsTab,
  type DrillParent,
} from '../../utils/analyticsTabState'
import {
  currentMonth,
  useResolvedRange,
  type PeriodTab,
  type SelectedMonth,
} from '../../utils/periodFilter'
import type { Currency } from '../../utils/formatCurrency'
import { AnalyticsChartsTab } from './AnalyticsChartsTab'
import { AnalyticsHistoryTab } from './AnalyticsHistoryTab'

function hydrateShellState(persisted: AnalyticsShellState | null): AnalyticsShellState {
  if (!persisted) {
    return createDefaultAnalyticsShellState()
  }
  return persisted
}

export function AnalyticsLayout() {
  const { t } = useTranslation()
  const persistedShell = useAnalyticsShellStore((state) => state.shell)
  const setPersistedShell = useAnalyticsShellStore((state) => state.setShell)
  const initialShell = useMemo(() => hydrateShellState(persistedShell), [persistedShell])

  const [activeTab, setActiveTabState] = useState<AnalyticsTab>(initialShell.activeTab)
  const [drillParent, setDrillParent] = useState<DrillParent | null>(initialShell.drillParent)
  const [historyCategoryFilter, setHistoryCategoryFilter] =
    useState<HistoryCategoryFilter | null>(initialShell.historyCategoryFilter)
  const [periodTab, setPeriodTab] = useState<PeriodTab>(initialShell.periodTab)
  const [selectedMonth, setSelectedMonth] = useState<SelectedMonth>(
    initialShell.selectedMonth ?? currentMonth(),
  )
  const [rangeFrom, setRangeFrom] = useState(initialShell.rangeFrom)
  const [rangeTo, setRangeTo] = useState(initialShell.rangeTo)
  const [rangeFromTouched, setRangeFromTouched] = useState(initialShell.rangeFromTouched)
  const [rangeToTouched, setRangeToTouched] = useState(initialShell.rangeToTouched)
  const currency: Currency = 'UZS'

  const buildShellState = useCallback(
    (): AnalyticsShellState => ({
      activeTab,
      drillParent,
      historyCategoryFilter,
      periodTab,
      selectedMonth,
      rangeFrom,
      rangeTo,
      rangeFromTouched,
      rangeToTouched,
      currency,
    }),
    [
      activeTab,
      drillParent,
      historyCategoryFilter,
      periodTab,
      selectedMonth,
      rangeFrom,
      rangeTo,
      rangeFromTouched,
      rangeToTouched,
      currency,
    ],
  )

  useEffect(() => {
    setPersistedShell(buildShellState())
  }, [buildShellState, setPersistedShell])

  const setActiveTab = useCallback((tab: AnalyticsTab) => {
    setActiveTabState(tab)
    setHistoryCategoryFilter((current) => historyFilterAfterTabSwitch(current, tab))
  }, [])

  const backTarget = analyticsBackTarget(activeTab, historyCategoryFilter)
  const handleNativeBack = useCallback(() => {
    if (backTarget) {
      setActiveTab(backTarget)
    }
  }, [backTarget, setActiveTab])
  useNativeBackButtonOverlay(backTarget !== null, handleNativeBack)

  const { range, rangeOrderInvalid } = useResolvedRange(
    periodTab,
    selectedMonth,
    rangeFrom,
    rangeTo,
  )
  const rangeKey = range ? `${range.dateFrom}|${range.dateTo}` : 'invalid'
  const rangeFetchEnabled = range !== null
  const fetchKey = `${rangeKey}|${currency}`

  const contextValue = useMemo(
    () => ({
      activeTab,
      setActiveTab,
      drillParent,
      setDrillParent,
      historyCategoryFilter,
      setHistoryCategoryFilter,
      periodTab,
      setPeriodTab,
      selectedMonth,
      setSelectedMonth,
      rangeFrom,
      setRangeFrom,
      rangeTo,
      setRangeTo,
      rangeFromTouched,
      setRangeFromTouched,
      rangeToTouched,
      setRangeToTouched,
      currency,
      range,
      rangeOrderInvalid,
      rangeFetchEnabled,
      rangeKey,
      fetchKey,
    }),
    [
      activeTab,
      setActiveTab,
      drillParent,
      historyCategoryFilter,
      periodTab,
      selectedMonth,
      rangeFrom,
      rangeTo,
      rangeFromTouched,
      rangeToTouched,
      currency,
      range,
      rangeOrderInvalid,
      rangeFetchEnabled,
      rangeKey,
      fetchKey,
    ],
  )

  return (
    <AnalyticsProvider value={contextValue}>
      <div className="page-content home-page analytics-page">
        <div className="analytics-page__period">
          <PeriodFilterControls
            periodTab={periodTab}
            onPeriodTabChange={setPeriodTab}
            selectedMonth={selectedMonth}
            onSelectedMonthChange={setSelectedMonth}
            rangeFrom={rangeFrom}
            rangeTo={rangeTo}
            onRangeFromChange={setRangeFrom}
            onRangeToChange={setRangeTo}
            rangeOrderInvalid={rangeOrderInvalid}
            periodHint={t('analytics.sharedPeriodHint')}
            leading={
              <div className="analytics-tabs" role="tablist" aria-label={t('analytics.title')}>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === 'charts'}
                  className={
                    activeTab === 'charts'
                      ? 'analytics-tabs__btn analytics-tabs__btn--active'
                      : 'analytics-tabs__btn'
                  }
                  onClick={() => setActiveTab('charts')}
                >
                  {t('analytics.tabCharts')}
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === 'history'}
                  className={
                    activeTab === 'history'
                      ? 'analytics-tabs__btn analytics-tabs__btn--active'
                      : 'analytics-tabs__btn'
                  }
                  onClick={() => setActiveTab('history')}
                >
                  {t('analytics.tabHistory')}
                </button>
              </div>
            }
          />
        </div>

        {activeTab === 'charts' ? <AnalyticsChartsTab /> : <AnalyticsHistoryTab />}
      </div>
    </AnalyticsProvider>
  )
}
