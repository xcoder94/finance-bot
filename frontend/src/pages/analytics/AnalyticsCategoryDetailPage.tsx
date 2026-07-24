import { useCallback, useMemo } from 'react'
import { Spinner, Text, Title } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation, useParams } from 'react-router-dom'

import { fetchExpensesByCategory } from '../../api/analytics'
import { fetchExpenseCategories } from '../../api/transactions'
import { BlockError, useFetchBlock } from '../../components/analytics/analyticsShared'
import { useAnalyticsContext } from '../../contexts/AnalyticsContext'
import {
  buildParentCategoryCards,
  sortSubcategoryEntriesByAmount,
  type SubcategoryDrillDownState,
} from '../../utils/analyticsCharts'
import {
  buildDrillDownStateForCard,
  fetchSubcategoryEntriesForCard,
  findParentCategoryCard,
} from '../../utils/analyticsDrillDown'
import { formatCurrency } from '../../utils/formatCurrency'
import { buildDisplayNameById, getDisplayName } from '../../utils/getDisplayName'

export function AnalyticsCategoryDetailPage() {
  const { t } = useTranslation()
  const location = useLocation()
  const { categoryKey } = useParams<{ categoryKey: string }>()
  const { currency, range, rangeFetchEnabled, fetchKey } = useAnalyticsContext()
  const routeState = location.state as SubcategoryDrillDownState | null

  const dataFetch = useFetchBlock(
    useCallback(async () => {
      if (!range || !categoryKey) {
        throw new Error('invalid range or category')
      }

      const [expenseCategories, expenseEntries] = await Promise.all([
        fetchExpenseCategories(),
        fetchExpensesByCategory(currency, range.dateFrom, range.dateTo),
      ])

      const expenseParentIds = expenseCategories
        .filter((category) => category.parent_id === null)
        .map((category) => category.id)
      const displayNameById = buildDisplayNameById(expenseCategories, t)
      const parentNameById = new Map(
        expenseCategories
          .filter((category) => category.parent_id === null)
          .map((category) => [category.id, getDisplayName(category, t)]),
      )

      const cards = buildParentCategoryCards(
        expenseEntries,
        expenseParentIds,
        t('analytics.other'),
        t,
        displayNameById,
      )
      const card = findParentCategoryCard(cards, categoryKey)

      if (!card) {
        return { missing: true as const, drillDown: null }
      }

      if (
        routeState &&
        routeState.categoryKey === categoryKey &&
        routeState.entries.length > 0
      ) {
        return { missing: false as const, drillDown: routeState }
      }

      const entries = await fetchSubcategoryEntriesForCard(
        card,
        currency,
        range.dateFrom,
        range.dateTo,
        parentNameById,
        t,
        displayNameById,
      )

      return {
        missing: false as const,
        drillDown: buildDrillDownStateForCard(
          card,
          entries,
          expenseCategories,
          expenseParentIds,
        ),
      }
    }, [range, categoryKey, currency, routeState, t]),
    `${fetchKey}|${categoryKey ?? 'missing'}`,
    rangeFetchEnabled && Boolean(categoryKey),
  )

  const listItems = useMemo(() => {
    if (dataFetch.state.status !== 'success' || !dataFetch.state.data.drillDown) {
      return []
    }
    return sortSubcategoryEntriesByAmount(dataFetch.state.data.drillDown.entries)
  }, [dataFetch.state])

  if (!categoryKey) {
    return <Navigate to="/analytics/categories" replace />
  }

  if (dataFetch.state.status === 'success' && dataFetch.state.data.missing) {
    return <Navigate to="/analytics/categories" replace />
  }

  return (
    <div className="page-content home-page analytics-page">
      <Title level="1" weight="2" className="home-page__title">
        {dataFetch.state.status === 'success' && dataFetch.state.data.drillDown
          ? dataFetch.state.data.drillDown.categoryName
          : t('analytics.categoriesTitle')}
      </Title>

      {!rangeFetchEnabled ? (
        <div className="analytics-empty-state">
          <Text>{t('analytics.noData')}</Text>
        </div>
      ) : null}

      {rangeFetchEnabled && dataFetch.state.status === 'loading' ? (
        <div className="home-block-loading" role="status" aria-live="polite">
          <Spinner size="m" aria-hidden="true" />
          <span className="visually-hidden">{t('home.loading')}</span>
        </div>
      ) : null}

      {rangeFetchEnabled && dataFetch.state.status === 'error' ? (
        <section className="analytics-card">
          <BlockError onRetry={dataFetch.retry} />
        </section>
      ) : null}

      {rangeFetchEnabled &&
      dataFetch.state.status === 'success' &&
      !dataFetch.state.data.missing &&
      listItems.length === 0 ? (
        <div className="analytics-empty-state">
          <Text>{t('analytics.noData')}</Text>
        </div>
      ) : null}

      {rangeFetchEnabled &&
      dataFetch.state.status === 'success' &&
      !dataFetch.state.data.missing &&
      listItems.length > 0 ? (
        <div className="analytics-subcategory-list">
          {listItems.map((item) => (
            <div key={`${item.parent_id ?? 'named'}-${item.subcategory_id}`} className="analytics-subcategory-list__item">
              <Text className="analytics-subcategory-list__label">{item.display_name}</Text>
              <Text className="analytics-subcategory-list__amount" weight="2">
                {formatCurrency(item.amount, currency)}
              </Text>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
