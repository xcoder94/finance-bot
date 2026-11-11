import { t } from '../i18n/t'
import { formatChartsEmptyMonth } from './analyticsChartsTab'
import { groupThousands } from './groupThousands'
import { shiftMonth, type PeriodTab, type SelectedMonth } from './periodFilter'

const DAY_MS = 86_400_000
const CHAR_WIDTH_EM = 0.62

/** Whole days covered by an inclusive range (end of day counts as the full day). */
export function rangeLengthDays(dateFromIso: string, dateToIso: string): number {
  const span = new Date(dateToIso).getTime() - new Date(dateFromIso).getTime()
  return Math.max(1, Math.round(span / DAY_MS))
}

export function comparisonPercent(total: number, prevTotal: number): number | null {
  if (prevTotal <= 0) {
    return null
  }
  return Math.round(((total - prevTotal) / prevTotal) * 100)
}

type ComparisonInput = {
  total: number
  prevTotal: number
  periodTab: PeriodTab
  selectedMonth: SelectedMonth
  rangeDays: number
}

/** «на 12% больше, чем в октябре»; null when the previous period had no expenses. */
export function buildComparisonLine(input: ComparisonInput): string | null {
  const pct = comparisonPercent(input.total, input.prevTotal)
  if (pct === null) {
    return null
  }
  const ref =
    input.periodTab === 'month'
      ? t('analytics.refMonth', {
          month: t(`months.prep.${shiftMonth(input.selectedMonth, -1).month}`).toLowerCase(),
        })
      : t('analytics.refDays', { count: input.rangeDays })
  if (pct === 0) {
    return t('analytics.compareSame', { ref })
  }
  return t(pct > 0 ? 'analytics.compareMore' : 'analytics.compareLess', { pct: groupThousands(Math.abs(pct)), ref })
}

export function buildHeadline(input: {
  periodTab: PeriodTab
  selectedMonth: SelectedMonth
  amount: string
}): string {
  if (input.periodTab === 'month') {
    return t('analytics.headline', {
      month: formatChartsEmptyMonth(input.selectedMonth),
      amount: input.amount,
    })
  }
  return t('analytics.headlineRange', { amount: input.amount })
}

export type DeltaLabel = { kind: 'new' | 'up' | 'down' | 'same'; text: string }

/** Row delta against the previous period: «+12%», «−5%», «новая». */
export function deltaLabel(amount: number, prevAmount: number): DeltaLabel {
  const pct = comparisonPercent(amount, prevAmount)
  if (pct === null) {
    return { kind: 'new', text: t('analytics.deltaNew') }
  }
  if (pct > 0) {
    return { kind: 'up', text: `+${pct}%` }
  }
  if (pct < 0) {
    return { kind: 'down', text: `−${Math.abs(pct)}%` }
  }
  return { kind: 'same', text: t('analytics.deltaSame') }
}

export function formatSharePercent(value: number): string {
  const text = Number.isInteger(value) ? String(value) : value.toFixed(1).replace('.', ',')
  return `${text}%`
}

/** Font size (px) so the centre amount stays inside the ring's inner diameter. */
export function donutCenterFontSize(text: string, innerDiameterPx: number): number {
  const fit = Math.floor(innerDiameterPx / (Math.max(1, text.length) * CHAR_WIDTH_EM))
  return Math.max(9, Math.min(22, fit))
}
