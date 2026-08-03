import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts'
import { Text } from '@telegram-apps/telegram-ui'

import { shouldIgnoreDonutTap } from '../../utils/analyticsDrill'
import { formatPercent, type DonutSlice } from '../../utils/analyticsCharts'
import { formatAnalyticsAmountDigits } from '../../utils/analyticsChartsTab'

type CategoryDonutChartProps = {
  slices: DonutSlice[]
  emptyMessage?: string
  compact?: boolean
  layout?: 'vertical' | 'horizontal'
  onSliceActivate?: (key: string) => void
  centerLabel?: string
}

export function CategoryDonutChart({
  slices,
  emptyMessage,
  compact = false,
  layout = 'vertical',
  onSliceActivate,
  centerLabel,
}: CategoryDonutChartProps) {
  if (slices.length === 0) {
    if (!emptyMessage) {
      return null
    }

    return (
      <div className="analytics-empty-state">
        <Text>{emptyMessage}</Text>
      </div>
    )
  }

  const total = slices.reduce((sum, slice) => sum + slice.value, 0)
  const chartHeight = compact ? 128 : 220
  const innerRadius = compact ? 42 : 58
  const outerRadius = compact ? 52 : 88
  const isHorizontal = layout === 'horizontal'

  const handleSliceActivate = (key: string) => {
    if (!onSliceActivate || shouldIgnoreDonutTap(key)) {
      return
    }
    onSliceActivate(key)
  }

  const chart = (
    <div className="analytics-donut__chart-wrap">
      <ResponsiveContainer width="100%" height={chartHeight}>
        <PieChart>
          <Pie
            data={slices}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            paddingAngle={1}
            stroke="none"
          >
            {slices.map((slice) => {
              const isInteractive = onSliceActivate && !shouldIgnoreDonutTap(slice.key)
              return (
                <Cell
                  key={slice.key}
                  fill={slice.color}
                  onClick={() => handleSliceActivate(slice.key)}
                  style={{ cursor: isInteractive ? 'pointer' : 'default' }}
                />
              )
            })}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      {centerLabel ? (
        <div className="analytics-donut__center" aria-hidden="true">
          <Text className="analytics-donut__center-label">{centerLabel}</Text>
          <Text className="analytics-donut__center-value" weight="2">
            {formatAnalyticsAmountDigits(total)}
          </Text>
        </div>
      ) : null}
    </div>
  )

  const legend = (
    <div className="analytics-donut__legend">
      {slices.map((slice) => {
        const isInteractive = onSliceActivate && !shouldIgnoreDonutTap(slice.key)
        const itemClassName = isInteractive
          ? 'analytics-donut__legend-item analytics-donut__legend-item--interactive'
          : 'analytics-donut__legend-item'

        const content = (
          <>
            <span className="analytics-donut__legend-dot" style={{ backgroundColor: slice.color }} />
            <Text className="analytics-donut__legend-name">{slice.name}</Text>
            <Text className="analytics-donut__legend-percent">
              {formatPercent(slice.value, total)}
            </Text>
          </>
        )

        if (isInteractive) {
          return (
            <button
              key={slice.key}
              type="button"
              className={itemClassName}
              onClick={() => handleSliceActivate(slice.key)}
            >
              {content}
            </button>
          )
        }

        return (
          <div key={slice.key} className={itemClassName}>
            {content}
          </div>
        )
      })}
    </div>
  )

  return (
    <div
      className={[
        'analytics-donut',
        compact ? 'analytics-donut--compact' : '',
        isHorizontal ? 'analytics-donut--horizontal' : '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {isHorizontal ? (
        <>
          {chart}
          {legend}
        </>
      ) : (
        <>
          {chart}
          {legend}
        </>
      )}
    </div>
  )
}
