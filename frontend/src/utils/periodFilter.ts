import { useMemo } from 'react'

import { monthDateRange } from '../api/home'
import i18n from '../i18n'
import {
  isoDateToMaskedDate,
  isValidMaskedDate,
  maskedDateToUtcEndIso,
  maskedDateToUtcStartIso,
} from '../utils/transactionForm'

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
  return new Intl.DateTimeFormat(getLocale(), {
    month: 'long',
    year: 'numeric',
  }).format(new Date(selected.year, selected.month - 1, 1))
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

  if (!isValidMaskedDate(rangeFrom) || !isValidMaskedDate(rangeTo)) {
    return { range: null, rangeOrderInvalid: false }
  }

  const dateFrom = maskedDateToUtcStartIso(rangeFrom)
  const dateTo = maskedDateToUtcEndIso(rangeTo)
  if (!dateFrom || !dateTo) {
    return { range: null, rangeOrderInvalid: false }
  }

  if (dateFrom > dateTo) {
    return { range: null, rangeOrderInvalid: true }
  }

  return { range: { dateFrom, dateTo }, rangeOrderInvalid: false }
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
    rangeFrom: isoDateToMaskedDate(monthRange.dateFrom),
    rangeTo: isoDateToMaskedDate(monthRange.dateTo),
  }
}
