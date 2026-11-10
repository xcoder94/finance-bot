import { t } from '../i18n/t'
import { useMemo } from 'react'

import { monthDateRange } from '../api/home'
import i18n from '../i18n'
import { dayEndIso, dayStartIso, isValidIsoDate, tashkentDateOf, todayTashkent } from './dateChips'

function clampToToday(iso: string): string {
  const today = todayTashkent()
  return iso > today ? today : iso
}

export type PeriodTab = 'month' | 'range'

export type SelectedMonth = {
  year: number
  month: number
}

export type ResolvedRange = {
  dateFrom: string
  dateTo: string
}

export function currentMonth(): SelectedMonth {
  const now = new Date()
  return { year: now.getFullYear(), month: now.getMonth() + 1 }
}

export function shiftMonth(selected: SelectedMonth, delta: number): SelectedMonth {
  const date = new Date(selected.year, selected.month - 1 + delta, 1)
  return { year: date.getFullYear(), month: date.getMonth() + 1 }
}

export function getLocale(): string {
  return i18n.language.startsWith('uz') ? 'uz-UZ' : 'ru-RU'
}

export function formatMonthLabel(selected: SelectedMonth): string {
  if (i18n.language.startsWith('uz')) {
    return t('months.title', { month: t(`months.long.${selected.month}`), year: selected.year })
  }
  const text = new Intl.DateTimeFormat(getLocale(), {
    month: 'long',
    year: 'numeric',
  }).format(new Date(selected.year, selected.month - 1, 1))
  // first letter only (CSS `capitalize` would also turn «г.» into «Г.»)
  return text.charAt(0).toLocaleUpperCase(getLocale()) + text.slice(1)
}

export function formatShortMonthKey(monthKey: string): string {
  const [yearText, monthText] = monthKey.split('-')
  const year = Number(yearText)
  const month = Number(monthText)
  return new Intl.DateTimeFormat(getLocale(), {
    month: 'short',
  })
    .format(new Date(year, month - 1, 1))
    .replace('.', '')
}

export function resolveRange(
  periodTab: PeriodTab,
  selectedMonth: SelectedMonth,
  rangeFrom: string,
  rangeTo: string,
): { range: ResolvedRange | null; rangeOrderInvalid: boolean } {
  if (periodTab === 'month') {
    return { range: monthDateRange(selectedMonth.year, selectedMonth.month), rangeOrderInvalid: false }
  }

  if (!isValidIsoDate(rangeFrom) || !isValidIsoDate(rangeTo)) {
    return { range: null, rangeOrderInvalid: false }
  }

  if (rangeFrom > rangeTo) {
    return { range: null, rangeOrderInvalid: true }
  }

  return {
    range: { dateFrom: dayStartIso(rangeFrom), dateTo: dayEndIso(rangeTo) },
    rangeOrderInvalid: false,
  }
}

export function useResolvedRange(
  periodTab: PeriodTab,
  selectedMonth: SelectedMonth,
  rangeFrom: string,
  rangeTo: string,
) {
  return useMemo(
    () => resolveRange(periodTab, selectedMonth, rangeFrom, rangeTo),
    [periodTab, selectedMonth, rangeFrom, rangeTo],
  )
}

export function initializeRangeFromMonth(selectedMonth: SelectedMonth): {
  rangeFrom: string
  rangeTo: string
} {
  const monthRange = monthDateRange(selectedMonth.year, selectedMonth.month)
  return {
    rangeFrom: tashkentDateOf(monthRange.dateFrom),
    rangeTo: clampToToday(tashkentDateOf(monthRange.dateTo)),
  }
}
