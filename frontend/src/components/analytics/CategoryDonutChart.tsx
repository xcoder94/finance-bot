import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts'
import { Text } from '@telegram-apps/telegram-ui'

import { formatPercent, type DonutSlice } from '../../utils/analyticsCharts'

type CategoryDonutChartProps = {
  slices: DonutSlice[]
  emptyMessage: string
  compact?: boolean
}

export function CategoryDonutChart({ slices, emptyMessage, compact = false }: CategoryDonutChartProps) {
  if (slices.length === 0) {
    return (
      <div className="analytics-empty-state">
        <Text>{emptyMessage}</Text>
      </div>
    )
  }

  const total = slices.reduce((sum, slice) => sum + slice.value, 0)
  const chartHeight = compact ? 160 : 220
  const innerRadius = compact ? 42 : 58
  const outerRadius = compact ? 64 : 88

  return (
    <div className={`analytics-donut${compact ? ' analytics-donut--compact' : ''}`}>
      <div className="analytics-donut__chart">
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
              {slices.map((slice) => (
                <Cell key={slice.name} fill={slice.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="analytics-donut__legend">
        {slices.map((slice) => (
          <div key={slice.name} className="analytics-donut__legend-item">
            <span className="analytics-donut__legend-dot" style={{ backgroundColor: slice.color }} />
            <Text className="analytics-donut__legend-name">{slice.name}</Text>
            <Text className="analytics-donut__legend-percent">{formatPercent(slice.value, total)}</Text>
          </div>
        ))}
      </div>
    </div>
  )
}
