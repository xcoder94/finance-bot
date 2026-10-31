import { t } from '../i18n/t'

export type HomeMonth = {
  year: number
  month: number
}

const TASHKENT_TZ = 'Asia/Tashkent'

function assertMonth(month: number): void {
  if (!Number.isInteger(month) || month < 1 || month > 12) {
    throw new RangeError(`month must be 1–12, got ${month}`)
  }
}

export function monthShortLabel(month: number): string {
  assertMonth(month)
  return t(`months.short.${month}`)
}

export function emptyMonthTitle(month: number): string {
  assertMonth(month)
  return t('home.emptyMonth', { month: t(`months.prep.${month}`) })
}

export function opsCountLabel(count: number, month: number): string {
  assertMonth(month)
  if (count === 0) {
    return t('home.opsNone')
  }
  return t('home.opsCount', { count, monthShort: monthShortLabel(month) })
}

export function balanceMonthLabel(month: number): string {
  assertMonth(month)
  return t('home.balanceMonth', { month: monthShortLabel(month) })
}

export function formatMonthTitle(year: number, month: number): string {
  assertMonth(month)
  return t('months.title', { month: t(`months.long.${month}`), year })
}

export function currentMonthInTashkent(): HomeMonth {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: TASHKENT_TZ,
    year: 'numeric',
    month: 'numeric',
  }).formatToParts(new Date())

  return {
    year: Number(parts.find((part) => part.type === 'year')?.value),
    month: Number(parts.find((part) => part.type === 'month')?.value),
  }
}

export function shiftHomeMonth(selected: HomeMonth, delta: number): HomeMonth {
  const date = new Date(selected.year, selected.month - 1 + delta, 1)
  return { year: date.getFullYear(), month: date.getMonth() + 1 }
}
