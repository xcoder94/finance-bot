const DATE_DIGIT_COUNT = 8

function extractDigits(value: string): string {
  return value.replace(/\D/g, '')
}

function isValidMaskedDate(value: string): boolean {
  const digits = extractDigits(value)
  if (digits.length !== DATE_DIGIT_COUNT) {
    return false
  }

  const day = Number(digits.slice(0, 2))
  const month = Number(digits.slice(2, 4))
  const year = Number(digits.slice(4, 8))

  if (month < 1 || month > 12) {
    return false
  }

  const daysInMonth = new Date(year, month, 0).getDate()
  if (day < 1 || day > daysInMonth) {
    return false
  }

  return true
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

function maskedDateToCalendarDate(value: string): CalendarDate | null {
  if (!isValidMaskedDate(value)) {
    return null
  }

  const digits = extractDigits(value)
  return {
    day: Number(digits.slice(0, 2)),
    month: Number(digits.slice(2, 4)),
    year: Number(digits.slice(4, 8)),
  }
}

function calendarDateOrdinal(date: CalendarDate): number {
  return date.year * 10_000 + date.month * 100 + date.day
}

export function isMaskedDateOnOrAfterToday(value: string, now = new Date()): boolean {
  const parsed = maskedDateToCalendarDate(value)
  if (parsed === null) {
    return false
  }

  return calendarDateOrdinal(parsed) >= calendarDateOrdinal(toTashkentCalendarDate(now))
}

export type GoalDeadlineHintKey = 'goals.form.deadlineInvalid' | 'addTransaction.invalidDate'

export function goalDeadlineValidation(
  deadlineMasked: string,
  options: {
    mode: 'create' | 'edit'
    existingDeadlineMasked?: string
    now?: Date
  },
): { valid: boolean; hintKey: GoalDeadlineHintKey | null } {
  const hasDeadline = deadlineMasked.length > 0
  const formatValid = !hasDeadline || isValidMaskedDate(deadlineMasked)
  const notBackdated =
    !hasDeadline ||
    isMaskedDateOnOrAfterToday(deadlineMasked, options.now) ||
    (options.mode === 'edit' && deadlineMasked === options.existingDeadlineMasked)

  if (formatValid && notBackdated) {
    return { valid: true, hintKey: null }
  }

  if (!formatValid) {
    return { valid: false, hintKey: 'goals.form.deadlineInvalid' }
  }

  return { valid: false, hintKey: 'addTransaction.invalidDate' }
}
