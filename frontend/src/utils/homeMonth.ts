export const MONTH_SHORT = [
  'янв',
  'фев',
  'март',
  'апр',
  'май',
  'июнь',
  'июль',
  'август',
  'сен',
  'окт',
  'ноя',
  'дек',
] as const

export type HomeMonth = {
  year: number
  month: number
}

const TASHKENT_TZ = 'Asia/Tashkent'

export const MONTH_PREPOSITIONAL = [
  'январе',
  'феврале',
  'марте',
  'апреле',
  'мае',
  'июне',
  'июле',
  'августе',
  'сентябре',
  'октябре',
  'ноябре',
  'декабре',
] as const

function assertMonth(month: number): void {
  if (!Number.isInteger(month) || month < 1 || month > 12) {
    throw new RangeError(`month must be 1–12, got ${month}`)
  }
}

export function monthShortLabel(month: number): string {
  assertMonth(month)
  return MONTH_SHORT[month - 1]
}

export function emptyMonthTitle(month: number): string {
  assertMonth(month)
  return `В ${MONTH_PREPOSITIONAL[month - 1]} операций нет`
}

export function opsCountLabel(count: number, month: number): string {
  assertMonth(month)
  if (count === 0) {
    return 'нет операций'
  }
  return `${count} за ${monthShortLabel(month)}`
}

export function balanceMonthLabel(month: number): string {
  assertMonth(month)
  return `Остаток · ${monthShortLabel(month)}`
}

export function formatMonthTitle(year: number, month: number): string {
  assertMonth(month)
  const longMonth = new Intl.DateTimeFormat('ru-RU', { month: 'long' }).format(
    new Date(year, month - 1, 1),
  )
  const capitalized = longMonth.charAt(0).toUpperCase() + longMonth.slice(1)
  return `${capitalized} ${year}`
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
