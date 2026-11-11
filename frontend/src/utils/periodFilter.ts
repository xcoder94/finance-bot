import { useMemo } from 'react'

import { monthDateRange } from '../api/home'
import i18n from '../i18n'
import { formatMonthTitle, monthShortLabel } from './homeMonth'
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

/** The one month-label format for the whole app: «Ноябрь 2026» / «2026-yil noyabr». */
export function formatMonthLabel(selected: SelectedMonth): string {
  return formatMonthTitle(selected.year, selected.month)
}

/** Short month name from the app's own strings (RU and UZ), never Intl: «Ноя» / «Noy». */
export function formatShortMonthKey(monthKey: string): string {
  const month = Number(monthKey.split('-')[1])
  const label = monthShortLabel(month)
  return label.charAt(0).toLocaleUpperCase() + label.slice(1)
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
    rangeFrom: clampToToday(tashkentDateOf(monthRange.dateFrom)),
    rangeTo: clampToToday(tashkentDateOf(monthRange.dateTo)),
  }
}
