import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts'
import { Text } from '@telegram-apps/telegram-ui'

import { shouldIgnoreDonutTap } from '../../utils/analyticsDrill'
import { formatPercent, type DonutSlice } from '../../utils/analyticsCharts'
import { formatAnalyticsAmountDigits } from '../../utils/analyticsChartsTab'
import { deltaLabel, donutCenterFontSize } from '../../utils/analyticsComparison'

export const DONUT_HEIGHT = 200
const OUTER_RADIUS = 90
const INNER_RADIUS = 66
/** Usable width inside the ring (a little less than the inner diameter). */
const CENTER_FIT_WIDTH = 116

type CategoryDonutChartProps = {
  slices: DonutSlice[]
  emptyMessage?: string
  onSliceActivate?: (key: string) => void
  centerLabel?: string
  /** Show the delta to the previous period on each row. */
  showDelta?: boolean
}

export function CategoryDonutChart({
  slices,
  emptyMessage,
  onSliceActivate,
  centerLabel,
  showDelta = true,
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
  const totalText = formatAnalyticsAmountDigits(total)

  const handleSliceActivate = (key: string) => {
    if (!onSliceActivate || shouldIgnoreDonutTap(key)) {
      return
    }
    onSliceActivate(key)
  }

  return (
    <div className="analytics-donut">
      <div className="analytics-donut__chart-wrap" style={{ height: DONUT_HEIGHT }}>
        <ResponsiveContainer width="100%" height={DONUT_HEIGHT}>
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={INNER_RADIUS}
              outerRadius={OUTER_RADIUS}
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
            <Text
              className="analytics-donut__center-value"
              weight="2"
              style={{ fontSize: donutCenterFontSize(totalText, CENTER_FIT_WIDTH) }}
            >
              {totalText}
            </Text>
          </div>
        ) : null}
      </div>

      <div className="analytics-donut__legend">
        {slices.map((slice) => {
          const isInteractive = Boolean(onSliceActivate) && !shouldIgnoreDonutTap(slice.key)
          const delta =
            showDelta && slice.prev !== undefined ? deltaLabel(slice.value, slice.prev) : null
          const className = isInteractive
            ? 'analytics-donut__legend-item analytics-donut__legend-item--interactive'
            : 'analytics-donut__legend-item'

          const content = (
            <>
              <span className="analytics-donut__legend-dot" style={{ backgroundColor: slice.color }} />
              <span className="analytics-donut__legend-name" title={slice.name}>
                {slice.name}
              </span>
              <span className="analytics-donut__legend-amount">
                {formatAnalyticsAmountDigits(slice.value)}
              </span>
              <span className="analytics-donut__legend-percent">
                {formatPercent(slice.value, total)}
              </span>
              <span
                className={
                  delta
                    ? `analytics-donut__legend-delta analytics-donut__legend-delta--${delta.kind}`
                    : 'analytics-donut__legend-delta'
                }
              >
                {delta?.text ?? ''}
              </span>
              <span className="analytics-donut__legend-chevron" aria-hidden="true">
                {isInteractive ? '›' : ''}
              </span>
            </>
          )

          if (isInteractive) {
            return (
              <button
                key={slice.key}
                type="button"
                className={className}
                onClick={() => handleSliceActivate(slice.key)}
              >
                {content}
              </button>
            )
          }

          return (
            <div key={slice.key} className={className}>
              {content}
            </div>
          )
        })}
      </div>
    </div>
  )
}
