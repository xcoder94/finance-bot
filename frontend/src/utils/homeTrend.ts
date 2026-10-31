import { t } from '../i18n/t'
import type { TrendEntry } from '../api/analytics'
import { shiftHomeMonth, type HomeMonth } from './homeMonth'

export const TREND_MAX_BAR_PX = 40
export const TREND_MIN_BAR_PX = 2

export type TrendBar = {
  year: number
  month: number
  expense: number
  heightPx: number
  current: boolean
}

export function trendEndMonthParam(selected: HomeMonth): string {
  return `${selected.year}-${String(selected.month).padStart(2, '0')}`
}

export function buildTrend3(entries: TrendEntry[], selected: HomeMonth): TrendBar[] {
  const months = [-2, -1, 0].map((delta) => shiftHomeMonth(selected, delta))
  const expenses = months.map(({ year, month }) => {
    const key = trendEndMonthParam({ year, month })
    return entries.find((entry) => entry.month === key && entry.currency === 'UZS')?.expense ?? 0
  })
  const max = Math.max(...expenses)
  return months.map(({ year, month }, index) => ({
    year,
    month,
    expense: expenses[index],
    heightPx:
      max > 0 && expenses[index] > 0
        ? Math.max(TREND_MIN_BAR_PX, (expenses[index] / max) * TREND_MAX_BAR_PX)
        : TREND_MIN_BAR_PX,
    current: index === 2,
  }))
}

export function formatMillions(value: number): string {
  const hundredths = Math.round(value / 10_000) / 100
  return String(hundredths).replace('.', ',')
}

export function trendMonthLabel(month: number): string {
  return t(`months.trend.${month}`)
}
