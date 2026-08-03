import { useCallback, useMemo } from 'react'
import { Spinner, Text } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import {
  fetchExpensesByCategory,
  fetchExpensesBySubcategory,
  fetchSummaryForRange,
  fetchTrend,
  type SummaryResponse,
} from '../../api/analytics'
import { fetchExpenseCategories } from '../../api/transactions'
import { BlockError, useFetchBlock } from '../../components/analytics/analyticsShared'
import { CategoryDonutChart } from '../../components/analytics/CategoryDonutChart'
import { TrendChart } from '../../components/analytics/TrendChart'
import { WeekdayBarChart } from '../../components/analytics/WeekdayBarChart'
import { useAnalyticsContext } from '../../contexts/AnalyticsContext'
import { useAuthStore } from '../../store/authStore'
import { getCachedExpenseCategories } from '../../store/dataCacheStore'
import type { PerCurrencySummary } from '../../api/home'
import {
  buildSubcategoryDisplayEntries,
  buildTrendChartRows,
  getOrderedSubcategoryIdsForParent,
  prepareDonutSlices,
  prepareSubcategoryDonutSlices,
} from '../../utils/analyticsCharts'
import { twelveMonthKeysEndingAt } from '../../utils/analyticsPeriod'
import {
  historyFilterAfterSubcategoryTap,
  shouldIgnoreDonutTap,
} from '../../utils/analyticsDrill'
import {
  elapsedDaysInPeriod,
  extendCategoryColorMap,
  formatAnalyticsAmountDigits,
  formatChartsEmptyMonth,
  isChartsTabEmpty,
} from '../../utils/analyticsChartsTab'
import { OTHER_CATEGORY_COLOR_INDEX } from '../../utils/chartColors'
import { dayWordRu } from '../../utils/dayCountLabel'
import {
  formatCurrency,
  formatUsdTrendAxisAmount,
  type Currency,
} from '../../utils/formatCurrency'
import { buildDisplayNameById } from '../../utils/getDisplayName'
import { formatMonthLabel, formatShortMonthKey } from '../../utils/periodFilter'

function getSummaryEntry(
  summary: SummaryResponse | null,
  currency: PerCurrencySummary['currency'],
): PerCurrencySummary {
  const entry = summary?.by_currency.find((row) => row.currency === currency)
  return {
    currency,
    income: entry?.income ?? 0,
    expense: entry?.expense ?? 0,
    transfer_net: entry?.transfer_net ?? 0,
    net_change: entry?.net_change ?? 0,
    average_daily_expense: entry?.average_daily_expense ?? 0,
    most_expensive_weekday: entry?.most_expensive_weekday ?? null,
    most_expensive_weekday_average: entry?.most_expensive_weekday_average ?? 0,
  }
}

function formatMostExpensiveAmount(amount: number, currency: Currency): string {
  if (currency === 'USD') {
    return formatCurrency(amount, 'USD')
  }
  return `${formatAnalyticsAmountDigits(amount)} сум`
}

function ChartsSkeleton() {
  const { t } = useTranslation()

  return (
    <div className="analytics-charts-tab">
      <div className="analytics-charts-skeleton" role="status" aria-live="polite">
        <div className="analytics-charts-skeleton__donut" />
        <div className="analytics-charts-skeleton__legend">
          <div className="analytics-charts-skeleton__line" />
          <div className="analytics-charts-skeleton__line" />
          <div className="analytics-charts-skeleton__line" />
        </div>
        <span className="visually-hidden">{t('home.loading')}</span>
      </div>
      <div className="analytics-charts-skeleton__block" />
    </div>
  )
}

function ChartsEmptyCard({ monthLabel }: { monthLabel: string }) {
  const { t } = useTranslation()

  return (
    <div className="analytics-charts-tab">
      <div className="analytics-charts-empty">
        <div className="analytics-charts-empty__icon" aria-hidden="true" />
        <Text weight="2" className="analytics-charts-empty__title">
          {t('analytics.chartsEmptyTitle', { month: monthLabel })}
        </Text>
        <Text className="analytics-charts-empty__hint">{t('analytics.chartsEmptyHint')}</Text>
      </div>
    </div>
  )
}

export function AnalyticsChartsTab() {
  const { t } = useTranslation()
  const familyId = useAuthStore((state) => state.user?.familyBudgetId ?? '')
  const {
    selectedMonth,
    currency,
    range,
    rangeFetchEnabled,
    fetchKey,
    rangeKey,
    drillParent,
    setDrillParent,
    setHistoryCategoryFilter,
    setActiveTab,
  } = useAnalyticsContext()

  const categoriesFetch = useFetchBlock(
    useCallback(async () => {
      const expenseCategories = await getCachedExpenseCategories(familyId, fetchExpenseCategories)
      const expenseParentIds = expenseCategories
        .filter((category) => category.parent_id === null)
        .map((category) => category.id)
      const expenseDisplayNameById = buildDisplayNameById(expenseCategories, t)
      return {
        expenseCategories,
        expenseParentIds,
        expenseDisplayNameById,
      }
    }, [familyId, t]),
    'mount',
    true,
  )

  const expensesFetch = useFetchBlock(
    useCallback(() => {
      if (!range) {
        return Promise.reject(new Error('invalid range'))
      }
      return fetchExpensesByCategory(currency, range.dateFrom, range.dateTo)
    }, [range, currency]),
    fetchKey,
    rangeFetchEnabled,
    false,
  )

  const subcategoryFetchKey = drillParent ? `${fetchKey}|drill:${drillParent.id}` : 'no-drill'

  const subcategoriesFetch = useFetchBlock(
    useCallback(() => {
      if (!range || !drillParent) {
        return Promise.reject(new Error('invalid drill'))
      }
      return fetchExpensesBySubcategory(
        drillParent.id,
        currency,
        range.dateFrom,
        range.dateTo,
      )
    }, [range, currency, drillParent]),
    subcategoryFetchKey,
    rangeFetchEnabled && drillParent !== null,
    false,
  )

  const summaryFetch = useFetchBlock(
    useCallback(() => {
      if (!range) {
        return Promise.reject(new Error('invalid range'))
      }
      return fetchSummaryForRange(range.dateFrom, range.dateTo)
    }, [range]),
    rangeKey,
    rangeFetchEnabled,
    false,
  )

  const trendEndMonth = `${selectedMonth.year}-${String(selectedMonth.month).padStart(2, '0')}`

  const trendFetch = useFetchBlock(
    useCallback(() => fetchTrend(trendEndMonth), [trendEndMonth]),
    fetchKey,
    rangeFetchEnabled,
    false,
  )

  const categoryMaps =
    categoriesFetch.state.status === 'success' ? categoriesFetch.state.data : null

  const parentSlices = useMemo(() => {
    if (!categoryMaps || expensesFetch.state.status !== 'success') {
      return []
    }
    return prepareDonutSlices(
      expensesFetch.state.data,
      categoryMaps.expenseParentIds,
      extendCategoryColorMap(categoryMaps.expenseParentIds, []),
      t('analytics.other'),
      t,
      categoryMaps.expenseDisplayNameById,
    )
  }, [categoryMaps, expensesFetch.state, t])

  const subcategoryEntries = useMemo(() => {
    if (!drillParent || !categoryMaps || subcategoriesFetch.state.status !== 'success') {
      return []
    }
    const parentNameById = new Map([[drillParent.id, drillParent.name]])
    return buildSubcategoryDisplayEntries(
      subcategoriesFetch.state.data,
      false,
      parentNameById,
      t,
      drillParent.id,
      categoryMaps.expenseDisplayNameById,
    )
  }, [drillParent, categoryMaps, subcategoriesFetch.state, t])

  const subcategoryColorMap = useMemo(() => {
    if (!drillParent || !categoryMaps) {
      return new Map<string, number>()
    }
    const orderedIds = getOrderedSubcategoryIdsForParent(
      drillParent.id,
      categoryMaps.expenseCategories,
    )
    const apiIds = subcategoryEntries.map((entry) => entry.subcategory_id)
    return extendCategoryColorMap(orderedIds, apiIds)
  }, [drillParent, categoryMaps, subcategoryEntries])

  const drillSlices = useMemo(() => {
    if (!drillParent || subcategoryEntries.length === 0) {
      return []
    }
    const orderedIds = Array.from(subcategoryColorMap.keys())
    return prepareSubcategoryDonutSlices(
      subcategoryEntries,
      orderedIds,
      subcategoryColorMap,
      t('analytics.other'),
    )
  }, [drillParent, subcategoryEntries, subcategoryColorMap, t])

  const donutSlices = drillParent ? drillSlices : parentSlices

  const summaryData: SummaryResponse | null =
    summaryFetch.state.status === 'success' ? summaryFetch.state.data : null
  const summaryEntry = getSummaryEntry(summaryData, currency)

  const trendRows = useMemo(() => {
    const entries = trendFetch.state.status === 'success' ? trendFetch.state.data : []
    return buildTrendChartRows(
      entries,
      currency,
      twelveMonthKeysEndingAt(selectedMonth),
      formatShortMonthKey,
    )
  }, [trendFetch.state, currency, selectedMonth])

  const weekdayLabels = [
    t('analytics.weekdayMon'),
    t('analytics.weekdayTue'),
    t('analytics.weekdayWed'),
    t('analytics.weekdayThu'),
    t('analytics.weekdayFri'),
    t('analytics.weekdaySat'),
    t('analytics.weekdaySun'),
  ]

  const weekdayRows = useMemo(() => {
    const weekdayAmounts = summaryData?.day_of_week_expense[currency] ?? [0, 0, 0, 0, 0, 0, 0]
    return weekdayLabels.map((label, index) => ({
      label,
      amount: weekdayAmounts[index] ?? 0,
    }))
  }, [summaryData, currency, weekdayLabels])

  const elapsedDays = range ? elapsedDaysInPeriod(range.dateFrom, range.dateTo) : 0

  const drillTotal = useMemo(() => {
    if (!drillParent) {
      return 0
    }
    if (subcategoriesFetch.state.status === 'success') {
      return subcategoriesFetch.state.data.reduce((sum, entry) => sum + entry.amount, 0)
    }
    if (expensesFetch.state.status === 'success') {
      const parentEntry = expensesFetch.state.data.find(
        (entry) => entry.category_id === drillParent.id,
      )
      return parentEntry?.amount ?? 0
    }
    return 0
  }, [drillParent, subcategoriesFetch.state, expensesFetch.state])

  const handleSliceActivate = useCallback(
    (key: string) => {
      if (shouldIgnoreDonutTap(key)) {
        return
      }

      if (!drillParent) {
        const slice = parentSlices.find((item) => item.key === key)
        if (!slice) {
          return
        }
        setDrillParent({ id: key, name: slice.name })
        return
      }

      const slice = drillSlices.find((item) => item.key === key)
      const entry = subcategoryEntries.find((item) => item.subcategory_id === key)
      const colorIndex = subcategoryColorMap.get(key) ?? OTHER_CATEGORY_COLOR_INDEX
      const filter = historyFilterAfterSubcategoryTap(
        key,
        slice?.name ?? entry?.display_name ?? '',
        colorIndex,
      )
      setHistoryCategoryFilter(filter)
      setActiveTab('history')
    },
    [
      drillParent,
      parentSlices,
      drillSlices,
      subcategoryEntries,
      subcategoryColorMap,
      setDrillParent,
      setHistoryCategoryFilter,
      setActiveTab,
    ],
  )

  const coreLoading =
    categoriesFetch.state.status === 'loading' || expensesFetch.state.status === 'loading'
  const coreError =
    categoriesFetch.state.status === 'error' || expensesFetch.state.status === 'error'

  const expenseTotal = useMemo(() => {
    if (summaryFetch.state.status === 'success') {
      return summaryEntry.expense
    }
    if (expensesFetch.state.status === 'success') {
      return expensesFetch.state.data.reduce((sum, entry) => sum + entry.amount, 0)
    }
    return 0
  }, [summaryFetch.state, summaryEntry.expense, expensesFetch.state])

  const emptyMonthLabel = formatChartsEmptyMonth(selectedMonth)
  const sharesMonthLabel = formatMonthLabel(selectedMonth)
  const chartsEmpty = isChartsTabEmpty(expenseTotal, parentSlices.length)

  if (coreLoading) {
    return <ChartsSkeleton />
  }

  if (coreError) {
    return (
      <div className="analytics-charts-tab">
        <BlockError
          onRetry={() => {
            if (categoriesFetch.state.status === 'error') {
              categoriesFetch.retry()
            }
            if (expensesFetch.state.status === 'error') {
              expensesFetch.retry()
            }
          }}
        />
      </div>
    )
  }

  if (chartsEmpty) {
    return <ChartsEmptyCard monthLabel={emptyMonthLabel} />
  }

  const mostExpensiveWeekdayLabel =
    summaryEntry.most_expensive_weekday === null
      ? '—'
      : weekdayLabels[summaryEntry.most_expensive_weekday] ?? '—'

  const avgDailyCaptionKey =
    currency === 'USD' ? 'analytics.avgDailyCaptionUsd' : 'analytics.avgDailyCaption'

  const drillHint = drillParent ? t('analytics.drillHintSubcategory') : t('analytics.drillHintRoot')

  const donutLoading = drillParent !== null && subcategoriesFetch.state.status === 'loading'
  const donutError = drillParent !== null && subcategoriesFetch.state.status === 'error'

  return (
    <div className="analytics-charts-tab">
      <section className="analytics-charts-donut-card">
        {drillParent ? (
          <div className="analytics-charts-donut-card__drill">
            <div className="analytics-charts-donut-card__drill-head">
              <button
                type="button"
                className="analytics-charts-donut-card__back"
                onClick={() => setDrillParent(null)}
              >
                ‹
              </button>
              <Text weight="2" className="analytics-charts-donut-card__drill-name">
                {drillParent.name}
              </Text>
            </div>
            <Text weight="2" className="analytics-charts-donut-card__drill-sum">
              {formatAnalyticsAmountDigits(drillTotal)}
            </Text>
            <Text className="analytics-charts-donut-card__shares">
              {t('analytics.sharesInside', { month: sharesMonthLabel })}
            </Text>
          </div>
        ) : (
          <Text weight="2" className="analytics-charts-donut-card__title">
            {t('analytics.expensesByCategory')}
          </Text>
        )}

        {donutError ? (
          <BlockError onRetry={subcategoriesFetch.retry} />
        ) : donutLoading ? (
          <div className="home-block-loading" role="status" aria-live="polite">
            <Spinner size="m" aria-hidden="true" />
            <span className="visually-hidden">{t('home.loading')}</span>
          </div>
        ) : (
          <CategoryDonutChart
            slices={donutSlices}
            compact
            layout="horizontal"
            onSliceActivate={handleSliceActivate}
            centerLabel={t('home.expense')}
          />
        )}

        <Text className="analytics-charts-donut-card__hint">{drillHint}</Text>
      </section>

      <section className="analytics-charts-block">
        {trendFetch.state.status === 'error' ? (
          <BlockError onRetry={trendFetch.retry} />
        ) : trendFetch.state.status === 'loading' ? (
          <div className="home-block-loading" role="status" aria-live="polite">
            <Spinner size="m" aria-hidden="true" />
          </div>
        ) : (
          <TrendChart
            rows={trendRows}
            incomeLabel={t('home.income')}
            expenseLabel={t('home.expense')}
            title={t('analytics.trendTitle')}
            unit={currency === 'USD' ? t('analytics.trendUnitUsd') : t('analytics.trendUnitUzs')}
            yAxisTickFormatter={
              currency === 'USD' ? formatUsdTrendAxisAmount : undefined
            }
          />
        )}
      </section>

      <div className="analytics-charts-tiles">
        <div className="analytics-charts-tile">
          <Text className="analytics-charts-tile__label">{t('analytics.avgDaily')}</Text>
          {summaryFetch.state.status === 'loading' ? (
            <Spinner size="s" />
          ) : (
            <>
              <Text weight="2" className="analytics-charts-tile__value">
                {formatAnalyticsAmountDigits(summaryEntry.average_daily_expense)}
              </Text>
              <Text className="analytics-charts-tile__caption">
                {t(avgDailyCaptionKey, {
                  count: elapsedDays,
                  dayWord: dayWordRu(elapsedDays),
                })}
              </Text>
            </>
          )}
        </div>

        <div className="analytics-charts-tile">
          <Text className="analytics-charts-tile__label">{t('analytics.mostExpensiveDay')}</Text>
          {summaryFetch.state.status === 'loading' ? (
            <Spinner size="s" />
          ) : (
            <>
              <Text weight="2" className="analytics-charts-tile__value">
                {mostExpensiveWeekdayLabel}
              </Text>
              <Text className="analytics-charts-tile__caption">
                {t('analytics.mostExpensiveCaption', {
                  amount: formatMostExpensiveAmount(
                    summaryEntry.most_expensive_weekday_average,
                    currency,
                  ),
                })}
              </Text>
            </>
          )}
        </div>
      </div>

      <section className="analytics-charts-block">
        <Text weight="2" className="analytics-charts-block__title">
          {t('analytics.weekdayExpenses')}
        </Text>
        {summaryFetch.state.status === 'error' ? (
          <BlockError onRetry={summaryFetch.retry} />
        ) : summaryFetch.state.status === 'loading' ? (
          <div className="home-block-loading" role="status" aria-live="polite">
            <Spinner size="m" aria-hidden="true" />
          </div>
        ) : (
          <WeekdayBarChart rows={weekdayRows} barColor="var(--acc)" />
        )}
      </section>
    </div>
  )
}
