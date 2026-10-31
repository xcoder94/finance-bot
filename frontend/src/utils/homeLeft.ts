import type { SummaryResponse } from '../api/home'
import type { HomeMonth } from './homeMonth'

const TASHKENT_TZ = 'Asia/Tashkent'

function tashkentToday(now: Date): { year: number; month: number; day: number } {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: TASHKENT_TZ,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
  }).formatToParts(now)
  const pick = (type: string) => Number(parts.find((part) => part.type === type)?.value)
  return { year: pick('year'), month: pick('month'), day: pick('day') }
}

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate()
}

/**
 * Days until the end of the selected month, today included (Tashkent calendar).
 * Past month -> null (no daily allowance); future month -> all of its days.
 */
export function daysLeftInMonth(now: Date, selected: HomeMonth): number | null {
  const today = tashkentToday(now)
  const selectedIndex = selected.year * 12 + selected.month
  const todayIndex = today.year * 12 + today.month
  if (selectedIndex < todayIndex) {
    return null
  }
  const total = daysInMonth(selected.year, selected.month)
  if (selectedIndex > todayIndex) {
    return total
  }
  return total - today.day + 1
}

/** remaining / days, magnitude rounded down to 100 so'm; null when there is no divisor. */
export function perDayAllowance(remaining: number, days: number | null): number | null {
  if (days === null || days <= 0) {
    return null
  }
  const raw = remaining / days
  const rounded = Math.floor(Math.abs(raw) / 100) * 100
  return raw < 0 && rounded > 0 ? -rounded : rounded
}

/** income - expense of the UZS row (net_change includes transfers and must not be used). */
export function remainingFromSummary(summary: SummaryResponse): number {
  const row = summary.by_currency.find((entry) => entry.currency === 'UZS')
  return row ? row.income - row.expense : 0
}
