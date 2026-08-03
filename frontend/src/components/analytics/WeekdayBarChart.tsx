import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { formatCompactAxisAmount } from '../../utils/formatCurrency'

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

export type WeekdayChartRow = {
  label: string
  amount: number
}

type WeekdayBarChartProps = {
  rows: WeekdayChartRow[]
  barColor?: string
}

export function WeekdayBarChart({
  rows,
  barColor = EXPENSE_COLOR,
}: WeekdayBarChartProps) {
  return (
    <div className="analytics-chart analytics-chart--wide">
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={rows} margin={CHART_MARGIN}>
          <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tick={AXIS_TICK}
            axisLine={{ stroke: AXIS_COLOR }}
            tickLine={{ stroke: AXIS_COLOR }}
          />
          <YAxis
            tick={AXIS_TICK}
            axisLine={{ stroke: AXIS_COLOR }}
            tickLine={{ stroke: AXIS_COLOR }}
            width={Y_AXIS_WIDTH}
            tickFormatter={formatCompactAxisAmount}
          />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelStyle={TOOLTIP_TEXT_STYLE}
            itemStyle={TOOLTIP_TEXT_STYLE}
            cursor={{ fill: 'var(--app-chart-cursor)' }}
          />
          <Bar dataKey="amount" fill={barColor} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
