import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { AnalyticsCard } from '../../components/analytics/analyticsShared'
import { CategoryDonutChart } from '../../components/analytics/CategoryDonutChart'
import {
  prepareSubcategoryDonutSlices,
  sortSubcategoryEntriesByAmount,
} from '../../utils/analyticsCharts'
import type { CardSubcategoryData } from '../../utils/analyticsDrillDown'

type CategoryDrillDownCardProps = {
  data: CardSubcategoryData
}

export function CategoryDrillDownCard({ data }: CategoryDrillDownCardProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { card, drillDown } = data

  const slices = useMemo(
    () =>
      prepareSubcategoryDonutSlices(
        sortSubcategoryEntriesByAmount(drillDown.entries),
        drillDown.orderedSubcategoryIds,
        drillDown.colorMap,
        t('analytics.other'),
      ),
    [drillDown, t],
  )

  return (
    <AnalyticsCard
      title={card.name}
      loading={false}
      error={false}
      onClick={() => navigate(`/analytics/categories/${drillDown.categoryKey}`, { state: drillDown })}
      compact
    >
      <CategoryDonutChart slices={slices} emptyMessage={t('analytics.noData')} compact />
    </AnalyticsCard>
  )
}
