import { t } from '../i18n/t'
import i18n from '../i18n'
import type { SelectedMonth } from './periodFilter'

export function isChartsTabEmpty(expenseTotal: number, sliceCount: number): boolean {
  return expenseTotal <= 0 && sliceCount === 0
}

type CalendarDate = {
  year: number
  month: number
  day: number
}

function toTashkentCalendarDate(date: Date): CalendarDate {
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tashkent',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
  const [year, month, day] = formatter.format(date).split('-').map(Number)
  return { year, month, day }
}

function calendarDateOrdinal(date: CalendarDate): number {
  return date.year * 10000 + date.month * 100 + date.day
}

function daysBetweenInclusive(from: CalendarDate, to: CalendarDate): number {
  const start = Date.UTC(from.year, from.month - 1, from.day)
  const end = Date.UTC(to.year, to.month - 1, to.day)
  return Math.round((end - start) / 86_400_000) + 1
}

export function elapsedDaysInPeriod(
  dateFromIso: string,
  dateToIso: string,
  now = new Date(),
): number {
  const from = toTashkentCalendarDate(new Date(dateFromIso))
  const to = toTashkentCalendarDate(new Date(dateToIso))
  const today = toTashkentCalendarDate(now)
  const effectiveEndOrdinal = Math.min(calendarDateOrdinal(to), calendarDateOrdinal(today))
  const fromOrdinal = calendarDateOrdinal(from)

  if (effectiveEndOrdinal < fromOrdinal) {
    return 1
  }

  const effectiveEnd: CalendarDate =
    effectiveEndOrdinal === calendarDateOrdinal(to) ? to : today

  return daysBetweenInclusive(from, effectiveEnd)
}

export function formatChartsEmptyMonth(selected: SelectedMonth): string {
  const month = t(`months.long.${selected.month}`).toLowerCase()
  // UZ sentence starts with the month («Noyabr uchun…»); RU has «За ноябрь…»
  return i18n.language.startsWith('uz') ? month.charAt(0).toUpperCase() + month.slice(1) : month
}

export function formatAnalyticsAmountDigits(amount: number): string {
  const sign = amount < 0 ? '-' : ''
  const absolute = Math.abs(amount)
  const formatted = groupThousands(absolute)
  return `${sign}${formatted}`
}

import { buildCategoryColorIndexMap } from './chartColors'
import { groupThousands } from './groupThousands'

export function mergeCategoryIds(orderedIds: string[], additionalIds: string[]): string[] {
  const mergedIds = [...orderedIds]
  for (const id of additionalIds) {
    if (!mergedIds.includes(id)) {
      mergedIds.push(id)
    }
  }
  return mergedIds
}

export function extendCategoryColorMap(
  orderedIds: string[],
  additionalIds: string[],
  storedColorIndexById?: Map<string, number>,
): Map<string, number> {
  return buildCategoryColorIndexMap(
    mergeCategoryIds(orderedIds, additionalIds),
    storedColorIndexById,
  )
}
