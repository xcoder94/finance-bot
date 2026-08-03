import { useMemo, useState } from 'react'
import { Title } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import { PeriodFilterControls } from '../../components/PeriodFilterControls'
import { AnalyticsProvider } from '../../contexts/AnalyticsContext'
import type { HistoryCategoryFilter } from '../../utils/analyticsDrill'
import type { AnalyticsTab, DrillParent } from '../../utils/analyticsTabState'
import {
  currentMonth,
  useResolvedRange,
  type PeriodTab,
  type SelectedMonth,
} from '../../utils/periodFilter'
import type { Currency } from '../../utils/formatCurrency'
import { AnalyticsChartsContent } from './AnalyticsChartsContent'
import { AnalyticsHistoryTab } from './AnalyticsHistoryTab'

const CURRENCIES = ['UZS', 'USD'] as const

export function AnalyticsLayout() {
  const { t } = useTranslation()
  const [activeTab, setActiveTabState] = useState<AnalyticsTab>('charts')
  const [drillParent, setDrillParent] = useState<DrillParent | null>(null)
  const [historyCategoryFilter, setHistoryCategoryFilter] =
    useState<HistoryCategoryFilter | null>(null)
  const [periodTab, setPeriodTab] = useState<PeriodTab>('month')
  const [selectedMonth, setSelectedMonth] = useState<SelectedMonth>(currentMonth)
  const [rangeFrom, setRangeFrom] = useState('')
  const [rangeTo, setRangeTo] = useState('')
  const [rangeFromTouched, setRangeFromTouched] = useState(false)
  const [rangeToTouched, setRangeToTouched] = useState(false)
  const [currency, setCurrencyState] = useState<Currency>('UZS')

  const { range, rangeOrderInvalid } = useResolvedRange(
    periodTab,
    selectedMonth,
    rangeFrom,
    rangeTo,
  )
  const rangeKey = range ? `${range.dateFrom}|${range.dateTo}` : 'invalid'
  const rangeFetchEnabled = range !== null
  const fetchKey = `${rangeKey}|${currency}`

  const setActiveTab = setActiveTabState
  const setCurrency = setCurrencyState

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
      setCurrency,
      range,
      rangeOrderInvalid,
      rangeFetchEnabled,
      rangeKey,
      fetchKey,
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
        <Title level="1" weight="2" className="home-page__title analytics-page__title">
          {t('analytics.title')}
        </Title>

        <div className="analytics-toolbar">
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

          {activeTab === 'charts' ? (
            <div className="home-currency-chip" role="group" aria-label={t('home.summary')}>
              {CURRENCIES.map((item) => (
                <button
                  key={item}
                  type="button"
                  className={
                    currency === item
                      ? 'home-currency-chip__btn home-currency-chip__btn--active'
                      : 'home-currency-chip__btn'
                  }
                  onClick={() => setCurrency(item)}
                >
                  {item}
                </button>
              ))}
            </div>
          ) : null}
        </div>

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
            rangeFromTouched={rangeFromTouched}
            rangeToTouched={rangeToTouched}
            onRangeFromTouched={() => setRangeFromTouched(true)}
            onRangeToTouched={() => setRangeToTouched(true)}
            rangeOrderInvalid={rangeOrderInvalid}
            monthSelectorClassName="analytics-page__month-selector"
            periodHint={t('analytics.sharedPeriodHint')}
          />
        </div>

        {activeTab === 'charts' ? <AnalyticsChartsContent /> : <AnalyticsHistoryTab />}
      </div>
    </AnalyticsProvider>
  )
}
