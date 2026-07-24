import { useCallback } from 'react'
import { Spinner, Text, Title } from '@telegram-apps/telegram-ui'
import { useTranslation } from 'react-i18next'

import {
  BlockError,
  useFetchBlock,
} from '../../components/analytics/analyticsShared'
import { CategoryDrillDownCard } from './CategoryDrillDownCard'
import { useAnalyticsContext } from '../../contexts/AnalyticsContext'
import { buildParentCategoryCards } from '../../utils/analyticsCharts'
import { fetchCardSubcategoryData } from '../../utils/analyticsDrillDown'
import { fetchExpensesByCategory } from '../../api/analytics'
import { fetchExpenseCategories } from '../../api/transactions'
import { buildDisplayNameById, getDisplayName } from '../../utils/getDisplayName'

export function AnalyticsCategoriesPage() {
  const { t } = useTranslation()
  const { currency, range, rangeFetchEnabled, fetchKey } = useAnalyticsContext()

  const dataFetch = useFetchBlock(
    useCallback(async () => {
      if (!range) {
        throw new Error('invalid range')
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

      const cardData = await Promise.all(
        cards.map((card) =>
          fetchCardSubcategoryData(
            card,
            currency,
            range.dateFrom,
            range.dateTo,
            expenseCategories,
            expenseParentIds,
            parentNameById,
            t,
            displayNameById,
          ),
        ),
      )

      return cardData
    }, [range, currency, t]),
    fetchKey,
    rangeFetchEnabled,
  )

  const cardData = dataFetch.state.status === 'success' ? dataFetch.state.data : []

  return (
    <div className="page-content home-page analytics-page">
      <Title level="1" weight="2" className="home-page__title">
        {t('analytics.categoriesTitle')}
      </Title>

      <div className="analytics-page__cards">
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

        {rangeFetchEnabled && dataFetch.state.status === 'success' && cardData.length === 0 ? (
          <div className="analytics-empty-state">
            <Text>{t('analytics.noData')}</Text>
          </div>
        ) : null}

        {rangeFetchEnabled && dataFetch.state.status === 'success'
          ? cardData.map((data) => <CategoryDrillDownCard key={data.card.key} data={data} />)
          : null}
      </div>
    </div>
  )
}
