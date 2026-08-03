import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import type { TrendChartRow } from '../../utils/analyticsCharts'
import { formatCompactAxisAmount } from '../../utils/formatCurrency'
import { Text } from '@telegram-apps/telegram-ui'

const INCOME_COLOR = 'var(--app-color-income)'
const EXPENSE_COLOR = 'var(--app-color-expense)'
const AXIS_COLOR = 'var(--app-chart-axis)'
const GRID_COLOR = 'var(--app-chart-grid)'
const Y_AXIS_WIDTH = 64
const CHART_MARGIN = { top: 20, right: 8, left: 8, bottom: 0 }
const AXIS_TICK = { fill: AXIS_COLOR, fontSize: 12 }
const TOOLTIP_STYLE = {
  backgroundColor: 'var(--app-chart-tooltip-bg)',
  borderColor: 'var(--app-chart-tooltip-border)',
  borderRadius: 8,
  color: 'var(--app-chart-tooltip-text)',
}
const TOOLTIP_TEXT_STYLE = { color: 'var(--app-chart-tooltip-text)' }

type TrendChartProps = {
  rows: TrendChartRow[]
  incomeLabel: string
  expenseLabel: string
  title: string
  unit: string
  yAxisTickFormatter?: (value: number) => string
}

export function TrendChart({
  rows,
  incomeLabel,
  expenseLabel,
  title,
  unit,
  yAxisTickFormatter = formatCompactAxisAmount,
}: TrendChartProps) {
  return (
    <div className="analytics-trend-chart">
      <div className="analytics-trend-chart__header">
        <Text weight="2" className="analytics-trend-chart__title">{title}</Text>
        <Text className="analytics-trend-chart__unit">{unit}</Text>
      </div>
      <div className="analytics-chart">
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={rows} margin={CHART_MARGIN}>
            <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              tick={AXIS_TICK}
              axisLine={{ stroke: AXIS_COLOR }}
              tickLine={{ stroke: AXIS_COLOR }}
              interval={0}
              angle={-45}
              textAnchor="end"
              height={56}
            />
            <YAxis
              tick={AXIS_TICK}
              axisLine={{ stroke: AXIS_COLOR }}
              tickLine={{ stroke: AXIS_COLOR }}
              width={Y_AXIS_WIDTH}
              tickFormatter={yAxisTickFormatter}
            />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              labelStyle={TOOLTIP_TEXT_STYLE}
              itemStyle={TOOLTIP_TEXT_STYLE}
              cursor={{ fill: 'var(--app-chart-cursor)' }}
            />
            <Legend wrapperStyle={TOOLTIP_TEXT_STYLE} />
            <Bar dataKey="income" name={incomeLabel} fill={INCOME_COLOR} radius={[4, 4, 0, 0]} />
            <Bar dataKey="expense" name={expenseLabel} fill={EXPENSE_COLOR} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
