import { sumUnit } from '../../utils/currencyUnit'
import { useCallback, useMemo } from 'react'
import { Text } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import {
  fetchExpenseComparison,
  fetchExpensesByCategory,
  fetchIncomeByCategory,
  fetchExpensesBySubcategory,
  fetchSummaryForRange,
  fetchTrend,
  type SummaryResponse,
} from '../../api/analytics'
import { fetchPersonalSummary } from '../../api/home'
import { fetchExpenseCategories } from '../../api/transactions'
import { BlockError, useFetchBlock } from '../../components/analytics/analyticsShared'
import { CategoryDonutChart } from '../../components/analytics/CategoryDonutChart'
import { TrendChart } from '../../components/analytics/TrendChart'
import { WeekdayBarChart } from '../../components/analytics/WeekdayBarChart'
import { useAnalyticsContext } from '../../contexts/AnalyticsContext'
import { useAuthStore } from '../../store/authStore'
import { getCachedExpenseCategories, getCachedPersonalSummary } from '../../store/dataCacheStore'
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
  historyFilterForUncategorized,
  isUncategorizedKey,
  shouldIgnoreDonutTap,
} from '../../utils/analyticsDrill'
import {
  elapsedDaysInPeriod,
  extendCategoryColorMap,
  formatAnalyticsAmountDigits,
  formatChartsEmptyMonth,
  isChartsTabEmpty,
  mergeCategoryIds,
} from '../../utils/analyticsChartsTab'
import {
  getColorByIndex,
  OTHER_CATEGORY_COLOR_INDEX,
  resolveEffectiveColorIndices,
} from '../../utils/chartColors'
import {
  buildComparisonLine,
  buildHeadline,
  formatSharePercent,
  rangeLengthDays,
} from '../../utils/analyticsComparison'
import { dayWordRu } from '../../utils/dayCountLabel'
import { buildDisplayNameById, resolveCategoryAmountDisplayName } from '../../utils/getDisplayName'
import {
  chooseTrendAxisScale,
  formatTrendAxisTick,
  trendAxisCaption,
} from '../../utils/trendAxis'
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

function BlockSkeleton({ height = 120 }: { height?: number }) {
  const { t } = useTranslation()

  return (
    <div
      className="analytics-charts-skeleton__block"
      style={{ height }}
      role="status"
      aria-live="polite"
    >
      <span className="visually-hidden">{t('home.loading')}</span>
    </div>
  )
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

function ChartsEmptyCard({
  monthLabel,
  personalOnly,
}: {
  monthLabel: string
  personalOnly: boolean
}) {
  const { t } = useTranslation()

  if (personalOnly) {
    return (
      <div className="analytics-charts-tab">
        <div className="analytics-charts-empty">
          <div className="analytics-charts-empty__icon" aria-hidden="true" />
          <Text className="analytics-charts-empty__hint">{t('analytics.personalOnly')}</Text>
        </div>
      </div>
    )
  }

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
    periodTab,
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

  const comparisonFetch = useFetchBlock(
    useCallback(() => {
      if (!range) {
        return Promise.reject(new Error('invalid range'))
      }
      return fetchExpenseComparison(currency, range.dateFrom, range.dateTo)
    }, [range, currency]),
    fetchKey,
    rangeFetchEnabled,
    false,
  )

  const incomeFetch = useFetchBlock(
    useCallback(() => {
      if (!range) {
        return Promise.reject(new Error('invalid range'))
      }
      return fetchIncomeByCategory(currency, range.dateFrom, range.dateTo)
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
    const apiCategoryIds = expensesFetch.state.data
      .filter((entry) => entry.amount > 0)
      .flatMap((entry) => (entry.category_id === null ? [] : [entry.category_id]))
    const orderedParentIds = mergeCategoryIds(categoryMaps.expenseParentIds, apiCategoryIds)
    const effectiveIndices = resolveEffectiveColorIndices(categoryMaps.expenseCategories)
    return prepareDonutSlices(
      expensesFetch.state.data,
      orderedParentIds,
      effectiveIndices,
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
    const effectiveIndices = resolveEffectiveColorIndices(categoryMaps.expenseCategories)
    return extendCategoryColorMap(orderedIds, apiIds, effectiveIndices)
  }, [drillParent, categoryMaps, subcategoryEntries, subcategoriesFetch.state])

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

  const trendScale = useMemo(
    () =>
      chooseTrendAxisScale(Math.max(0, ...trendRows.flatMap((row) => [row.income, row.expense]))),
    [trendRows],
  )

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
      if (isUncategorizedKey(key)) {
        if (drillParent) {
          return
        }
        setHistoryCategoryFilter(historyFilterForUncategorized(t('analytics.uncategorized')))
        setActiveTab('history')
        return
      }

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
      t,
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

  const personalCheckEnabled =
    !coreLoading && !coreError && chartsEmpty && periodTab === 'month'
  const personalFetch = useFetchBlock(
    useCallback(
      () =>
        getCachedPersonalSummary(familyId, selectedMonth.year, selectedMonth.month, () =>
          fetchPersonalSummary(selectedMonth.year, selectedMonth.month),
        ),
      [familyId, selectedMonth],
    ),
    `${selectedMonth.year}-${selectedMonth.month}`,
    personalCheckEnabled,
    false,
  )
  const personalOnly =
    personalFetch.state.status === 'success' &&
    personalFetch.state.data.by_currency.some((row) => row.expense > 0 || row.income > 0)

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
    return <ChartsEmptyCard monthLabel={emptyMonthLabel} personalOnly={personalOnly} />
  }

  const hasOtherSlice = donutSlices.some((slice) => slice.key === 'other')
  const rootHint = drillParent ? null : t('analytics.hintRoot')

  const donutLoading = drillParent !== null && subcategoriesFetch.state.status === 'loading'
  const donutError = drillParent !== null && subcategoriesFetch.state.status === 'error'

  const headline = buildHeadline({
    periodTab,
    selectedMonth,
    amount: `${formatAnalyticsAmountDigits(expenseTotal)} ${sumUnit()}`,
  })
  const comparisonLine =
    comparisonFetch.state.status === 'success' && range
      ? buildComparisonLine({
          total: comparisonFetch.state.data.total,
          prevTotal: comparisonFetch.state.data.prev_total,
          periodTab,
          selectedMonth,
          rangeDays: rangeLengthDays(range.dateFrom, range.dateTo),
        })
      : null

  const incomeRows =
    incomeFetch.state.status === 'success'
      ? incomeFetch.state.data.filter((entry) => entry.amount > 0)
      : []

  const openParentHistory = () => {
    if (!drillParent) {
      return
    }
    const slice = parentSlices.find((item) => item.key === drillParent.id)
    setHistoryCategoryFilter({
      id: drillParent.id,
      name: drillParent.name,
      color: slice?.color ?? getColorByIndex(OTHER_CATEGORY_COLOR_INDEX),
    })
    setActiveTab('history')
  }

  return (
    <div className="analytics-charts-tab">
      <header className="analytics-charts-headline">
        <Text weight="2" className="analytics-charts-headline__title">
          {headline}
        </Text>
        {comparisonLine ? (
          <Text className="analytics-charts-headline__compare">{comparisonLine}</Text>
        ) : null}
      </header>

      <section className="analytics-charts-donut-card">
        {drillParent ? (
          <div className="analytics-charts-donut-card__drill">
            <nav className="analytics-charts-donut-card__drill-head" aria-label="breadcrumb">
              <button
                type="button"
                className="analytics-charts-donut-card__crumb"
                onClick={() => setDrillParent(null)}
              >
                {t('analytics.allExpenses')}
              </button>
              <span className="analytics-charts-donut-card__crumb-sep" aria-hidden="true">
                /
              </span>
              <Text weight="2" className="analytics-charts-donut-card__drill-name">
                {drillParent.name}
              </Text>
            </nav>
            <Text weight="2" className="analytics-charts-donut-card__drill-sum">
              {formatAnalyticsAmountDigits(drillTotal)}
            </Text>
            <Text className="analytics-charts-donut-card__shares">
              {t('analytics.sharesInside', { month: sharesMonthLabel })}
            </Text>
            <button
              type="button"
              className="analytics-charts-donut-card__all-ops"
              onClick={openParentHistory}
            >
              {t('analytics.allOpsOf', { name: drillParent.name })}
            </button>
          </div>
        ) : (
          <Text weight="2" className="analytics-charts-donut-card__title">
            {t('analytics.expensesByCategory')}
          </Text>
        )}

        {donutError ? (
          <BlockError onRetry={subcategoriesFetch.retry} />
        ) : donutLoading ? (
          <BlockSkeleton height={240} />
        ) : (
          <CategoryDonutChart
            slices={donutSlices}
            onSliceActivate={handleSliceActivate}
            centerLabel={t('home.expense')}
          />
        )}

        {rootHint ? (
          <Text className="analytics-charts-donut-card__hint">{rootHint}</Text>
        ) : null}
        {hasOtherSlice ? (
          <Text className="analytics-charts-donut-card__hint">{t('analytics.hintOther')}</Text>
        ) : null}
      </section>

      {incomeRows.length > 0 ? (
        <section className="analytics-charts-block analytics-income-block">
          <Text weight="2" className="analytics-charts-block__title">
            {t('analytics.incomeByCategory')}
          </Text>
          <div className="analytics-income-list">
            {incomeRows.map((entry) => (
              <div
                key={entry.category_id ?? entry.category_name}
                className="analytics-donut__legend-item analytics-income-row"
              >
                <span
                  className="analytics-donut__legend-dot"
                  style={{ backgroundColor: getColorByIndex(entry.color_index ?? 1) }}
                />
                <span className="analytics-donut__legend-name" title={entry.category_name}>
                  {entry.category_id
                    ? resolveCategoryAmountDisplayName(
                        { ...entry, category_id: entry.category_id },
                        undefined,
                        t,
                      )
                    : entry.category_name}
                </span>
                <span className="analytics-donut__legend-amount">
                  {formatAnalyticsAmountDigits(entry.amount)}
                </span>
                <span className="analytics-donut__legend-percent">
                  {formatSharePercent(entry.share_percent ?? 0)}
                </span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="analytics-charts-block">
        {trendFetch.state.status === 'error' ? (
          <BlockError onRetry={trendFetch.retry} />
        ) : trendFetch.state.status === 'loading' ? (
          <BlockSkeleton height={150} />
        ) : (
          <TrendChart
            rows={trendRows}
            incomeLabel={t('home.income')}
            expenseLabel={t('home.expense')}
            title={t('analytics.trendTitle')}
            unit={trendAxisCaption(trendScale, currency)}
            yAxisTickFormatter={(value) => formatTrendAxisTick(value, trendScale)}
          />
        )}
      </section>

      <div className="analytics-charts-tiles">
        <div className="analytics-charts-tile">
          <Text className="analytics-charts-tile__label">{t('analytics.avgDaily')}</Text>
          {summaryFetch.state.status === 'loading' ? (
            <BlockSkeleton height={36} />
          ) : (
            <>
              <Text weight="2" className="analytics-charts-tile__value">
                {formatAnalyticsAmountDigits(summaryEntry.average_daily_expense)}
              </Text>
              <Text className="analytics-charts-tile__caption">
                {t('analytics.avgDailyCaption', {
                  count: elapsedDays,
                  dayWord: dayWordRu(elapsedDays),
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
          <BlockSkeleton height={120} />
        ) : (
          <WeekdayBarChart rows={weekdayRows} barColor="var(--acc)" />
        )}
      </section>
    </div>
  )
}
