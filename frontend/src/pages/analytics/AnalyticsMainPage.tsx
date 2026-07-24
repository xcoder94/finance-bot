import { useCallback, useMemo } from 'react'
import { SegmentedControl, Text, Title } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import {
  fetchExpensesByCategory,
  fetchIncomeByCategory,
  fetchSummaryForRange,
  fetchTrend,
  type SummaryResponse,
} from '../../api/analytics'
import { fetchExpenseCategories, fetchIncomeCategories } from '../../api/transactions'
import {
  AnalyticsCard,
  MetricValue,
  useFetchBlock,
} from '../../components/analytics/analyticsShared'
import { CategoryDonutChart } from '../../components/analytics/CategoryDonutChart'
import { TrendChart } from '../../components/analytics/TrendChart'
import { WeekdayBarChart } from '../../components/analytics/WeekdayBarChart'
import { PeriodFilterControls } from '../../components/PeriodFilterControls'
import { useAnalyticsContext } from '../../contexts/AnalyticsContext'
import { useAuthStore } from '../../store/authStore'
import {
  getCachedExpenseCategories,
  getCachedIncomeCategories,
} from '../../store/dataCacheStore'
import { buildCategoryColorIndexMap } from '../../utils/chartColors'
import {
  buildDisplayNameById,
} from '../../utils/getDisplayName'
import {
  buildTrendChartRows,
  countNonzeroCategories,
  getLast12MonthKeys,
  prepareDonutSlices,
} from '../../utils/analyticsCharts'
import { formatShortMonthKey } from '../../utils/periodFilter'
import { formatCurrency } from '../../utils/formatCurrency'
import type { PerCurrencySummary } from '../../api/home'

const CURRENCIES = ['UZS', 'USD'] as const

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
  }
}

export function AnalyticsMainPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const familyId = useAuthStore((state) => state.user?.familyBudgetId ?? '')
  const {
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
    fetchKey,
    rangeKey,
  } = useAnalyticsContext()

  const categoriesFetch = useFetchBlock(
    useCallback(async () => {
      const [expenseCategories, incomeCategories] = await Promise.all([
        getCachedExpenseCategories(familyId, fetchExpenseCategories),
        getCachedIncomeCategories(familyId, fetchIncomeCategories),
      ])
      const expenseParentIds = expenseCategories
        .filter((category) => category.parent_id === null)
        .map((category) => category.id)
      const incomeCategoryIds = incomeCategories.map((category) => category.id)
      const expenseDisplayNameById = buildDisplayNameById(expenseCategories, t)
      const incomeDisplayNameById = buildDisplayNameById(incomeCategories, t)
      return {
        expenseParentIds,
        incomeCategoryIds,
        expenseColorMap: buildCategoryColorIndexMap(expenseParentIds),
        incomeColorMap: buildCategoryColorIndexMap(incomeCategoryIds),
        expenseDisplayNameById,
        incomeDisplayNameById,
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
  )

  const trendFetch = useFetchBlock(useCallback(() => fetchTrend(), []), 'mount', true)

  const categoryMaps =
    categoriesFetch.state.status === 'success' ? categoriesFetch.state.data : null

  const expenseSlices = useMemo(() => {
    if (!categoryMaps || expensesFetch.state.status !== 'success') {
      return []
    }
    return prepareDonutSlices(
      expensesFetch.state.data,
      categoryMaps.expenseParentIds,
      categoryMaps.expenseColorMap,
      t('analytics.other'),
      t,
      categoryMaps.expenseDisplayNameById,
    )
  }, [categoryMaps, expensesFetch.state, t])

  const incomeSlices = useMemo(() => {
    if (!categoryMaps || incomeFetch.state.status !== 'success') {
      return []
    }
    return prepareDonutSlices(
      incomeFetch.state.data,
      categoryMaps.incomeCategoryIds,
      categoryMaps.incomeColorMap,
      t('analytics.other'),
      t,
      categoryMaps.incomeDisplayNameById,
    )
  }, [categoryMaps, incomeFetch.state, t])

  const showIncomeDonut =
    incomeFetch.state.status !== 'success' ||
    countNonzeroCategories(incomeFetch.state.data) >= 3

  const trendRows = useMemo(() => {
    const entries = trendFetch.state.status === 'success' ? trendFetch.state.data : []
    return buildTrendChartRows(
      entries,
      currency,
      getLast12MonthKeys(),
      formatShortMonthKey,
    )
  }, [trendFetch.state, currency])

  const summaryData: SummaryResponse | null =
    summaryFetch.state.status === 'success' ? summaryFetch.state.data : null
  const summaryEntry = getSummaryEntry(summaryData, currency)
  const weekdayRows = useMemo(() => {
    const weekdayAmounts = summaryData?.day_of_week_expense[currency] ?? [0, 0, 0, 0, 0, 0, 0]
    return [
      t('analytics.weekdayMon'),
      t('analytics.weekdayTue'),
      t('analytics.weekdayWed'),
      t('analytics.weekdayThu'),
      t('analytics.weekdayFri'),
      t('analytics.weekdaySat'),
      t('analytics.weekdaySun'),
    ].map((label, index) => ({
      label,
      amount: weekdayAmounts[index] ?? 0,
    }))
  }, [summaryData, currency, t])

  const canDrillDown =
    categoriesFetch.state.status === 'success' &&
    expensesFetch.state.status === 'success' &&
    expenseSlices.length > 0
  const expenseDonutLoading =
    categoriesFetch.state.status === 'loading' || expensesFetch.state.status === 'loading'
  const expenseDonutError =
    categoriesFetch.state.status === 'error' || expensesFetch.state.status === 'error'
  const incomeDonutLoading =
    categoriesFetch.state.status === 'loading' || incomeFetch.state.status === 'loading'
  const incomeDonutError =
    categoriesFetch.state.status === 'error' || incomeFetch.state.status === 'error'

  const retryExpenseDonut = () => {
    if (categoriesFetch.state.status === 'error') {
      categoriesFetch.retry()
    }
    if (expensesFetch.state.status === 'error') {
      expensesFetch.retry()
    }
  }

  const retryIncomeDonut = () => {
    if (categoriesFetch.state.status === 'error') {
      categoriesFetch.retry()
    }
    if (incomeFetch.state.status === 'error') {
      incomeFetch.retry()
    }
  }

  return (
    <div className="page-content home-page analytics-page">
      <Title level="1" weight="2" className="home-page__title">
        {t('analytics.title')}
      </Title>

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
      />

      <div className="segmented-control-wrap home-page__currency-toggle">
        <SegmentedControl>
          {CURRENCIES.map((item) => (
            <SegmentedControl.Item
              key={item}
              selected={currency === item}
              onClick={() => setCurrency(item)}
            >
              {item}
            </SegmentedControl.Item>
          ))}
        </SegmentedControl>
      </div>

      <div className="analytics-page__cards">
        <AnalyticsCard
          title={t('analytics.expensesByCategory')}
          loading={expenseDonutLoading}
          error={expenseDonutError}
          onRetry={retryExpenseDonut}
          onClick={canDrillDown ? () => navigate('/analytics/categories') : undefined}
        >
          <CategoryDonutChart
            slices={expenseSlices}
            emptyMessage={t('analytics.noData')}
          />
        </AnalyticsCard>

        {showIncomeDonut ? (
          <AnalyticsCard
            title={t('analytics.incomeByCategory')}
            loading={incomeDonutLoading}
            error={incomeDonutError}
            onRetry={retryIncomeDonut}
          >
            <CategoryDonutChart
              slices={incomeSlices}
              emptyMessage={t('analytics.noData')}
            />
          </AnalyticsCard>
        ) : null}

        <AnalyticsCard
          title={t('analytics.monthlyTrend')}
          loading={trendFetch.state.status === 'loading'}
          error={trendFetch.state.status === 'error'}
          onRetry={trendFetch.retry}
        >
          <TrendChart
            rows={trendRows}
            incomeLabel={t('home.income')}
            expenseLabel={t('home.expense')}
          />
        </AnalyticsCard>

        <AnalyticsCard
          title={t('analytics.summaryTitle')}
          loading={summaryFetch.state.status === 'loading'}
          error={summaryFetch.state.status === 'error'}
          onRetry={summaryFetch.retry}
        >
          <div className="analytics-summary">
            <div className="home-summary__row">
              <div className="home-metric-card">
                <Text className="home-metric-card__label">{t('home.income')}</Text>
                <MetricValue className="home-metric-card__value home-metric-card__value--income">
                  {formatCurrency(summaryEntry.income, currency)}
                </MetricValue>
              </div>
              <div className="home-metric-card">
                <Text className="home-metric-card__label">{t('home.expense')}</Text>
                <MetricValue className="home-metric-card__value home-metric-card__value--expense">
                  {formatCurrency(summaryEntry.expense, currency)}
                </MetricValue>
              </div>
            </div>
            <div className="home-summary__row">
              <div className="home-metric-card">
                <Text className="home-metric-card__label">{t('analytics.transferNet')}</Text>
                <MetricValue className="home-metric-card__value home-metric-card__value--transfer">
                  {formatCurrency(summaryEntry.transfer_net, currency)}
                </MetricValue>
              </div>
              <div className="home-metric-card">
                <Text className="home-metric-card__label">{t('analytics.netChange')}</Text>
                <MetricValue className="home-metric-card__value">
                  {formatCurrency(summaryEntry.net_change, currency)}
                </MetricValue>
              </div>
            </div>
            <div className="home-metric-card home-metric-card--wide">
              <Text className="home-metric-card__label">{t('analytics.averageDailyExpense')}</Text>
              <MetricValue className="home-metric-card__value home-metric-card__value--expense">
                {formatCurrency(summaryEntry.average_daily_expense, currency)}
              </MetricValue>
            </div>
          </div>
        </AnalyticsCard>

        <AnalyticsCard
          title={t('analytics.weekdayExpenses')}
          loading={summaryFetch.state.status === 'loading'}
          error={summaryFetch.state.status === 'error'}
          onRetry={summaryFetch.retry}
        >
          <WeekdayBarChart rows={weekdayRows} />
        </AnalyticsCard>
      </div>
    </div>
  )
}
