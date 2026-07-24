import { type Currency, formatCurrency } from './formatCurrency'

export const MAX_AMOUNT_DIGITS = 10
const DATETIME_DIGIT_COUNT = 12
const DATE_DIGIT_COUNT = 8

export function formatWalletLabel(name: string, currency: string): string {
  return `${name} (${currency})`
}

export function extractDigits(value: string): string {
  return value.replace(/\D/g, '')
}

export function formatThousandsDigits(digits: string): string {
  if (!digits) {
    return ''
  }
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
}

export function countDigitsBeforeCursor(formatted: string, cursorPos: number): number {
  return extractDigits(formatted.slice(0, cursorPos)).length
}

export function cursorPosAfterDigits(formatted: string, digitCount: number): number {
  if (digitCount <= 0) {
    return 0
  }

  let seen = 0
  for (let index = 0; index < formatted.length; index += 1) {
    if (/\d/.test(formatted[index])) {
      seen += 1
      if (seen === digitCount) {
        return index + 1
      }
    }
  }

  return formatted.length
}

export function insertDigitAt(digits: string, digitIndex: number, digit: string): string {
  return digits.slice(0, digitIndex) + digit + digits.slice(digitIndex)
}

export function deleteDigitBefore(digits: string, digitIndex: number): string {
  if (digitIndex <= 0) {
    return digits
  }
  return digits.slice(0, digitIndex - 1) + digits.slice(digitIndex)
}

export function deleteDigitAt(digits: string, digitIndex: number): string {
  return digits.slice(0, digitIndex) + digits.slice(digitIndex + 1)
}

export function deleteDigitRange(digits: string, startDigitIndex: number, endDigitIndex: number): string {
  return digits.slice(0, startDigitIndex) + digits.slice(endDigitIndex)
}

export function formatDateDigits(digits: string): string {
  const normalized = digits.slice(0, DATE_DIGIT_COUNT)
  let formatted = ''

  for (let index = 0; index < normalized.length; index += 1) {
    if (index === 2 || index === 4) {
      formatted += '.'
    }
    formatted += normalized[index]
  }

  return formatted
}

export function isValidMaskedDate(value: string): boolean {
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

export function maskedDateToUtcStartIso(value: string): string | null {
  if (!isValidMaskedDate(value)) {
    return null
  }

  const digits = extractDigits(value)
  const day = Number(digits.slice(0, 2))
  const month = Number(digits.slice(2, 4))
  const year = Number(digits.slice(4, 8))

  return new Date(Date.UTC(year, month - 1, day)).toISOString()
}

export function maskedDateToUtcEndIso(value: string): string | null {
  if (!isValidMaskedDate(value)) {
    return null
  }

  const digits = extractDigits(value)
  const day = Number(digits.slice(0, 2))
  const month = Number(digits.slice(2, 4))
  const year = Number(digits.slice(4, 8))

  return new Date(Date.UTC(year, month - 1, day, 23, 59, 59, 999)).toISOString()
}

export function isoDateToMaskedDate(iso: string): string {
  const date = new Date(iso)
  const digits = [
    String(date.getUTCDate()).padStart(2, '0'),
    String(date.getUTCMonth() + 1).padStart(2, '0'),
    String(date.getUTCFullYear()),
  ].join('')

  return formatDateDigits(digits)
}

export function formatDatetimeDigits(digits: string): string {
  const normalized = digits.slice(0, DATETIME_DIGIT_COUNT)
  let formatted = ''

  for (let index = 0; index < normalized.length; index += 1) {
    if (index === 2 || index === 4) {
      formatted += '.'
    }
    if (index === 8) {
      formatted += ', '
    }
    if (index === 10) {
      formatted += ':'
    }
    formatted += normalized[index]
  }

  return formatted
}

export function nowMaskedDatetimeValue(): string {
  const now = new Date()
  const digits = [
    String(now.getDate()).padStart(2, '0'),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getFullYear()),
    String(now.getHours()).padStart(2, '0'),
    String(now.getMinutes()).padStart(2, '0'),
  ].join('')

  return formatDatetimeDigits(digits)
}

export function isoDatetimeToMaskedDatetime(iso: string): string {
  const date = new Date(iso)
  const digits = [
    String(date.getDate()).padStart(2, '0'),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getFullYear()),
    String(date.getHours()).padStart(2, '0'),
    String(date.getMinutes()).padStart(2, '0'),
  ].join('')

  return formatDatetimeDigits(digits)
}

export function isValidMaskedDatetime(value: string): boolean {
  const digits = extractDigits(value)
  if (digits.length !== DATETIME_DIGIT_COUNT) {
    return false
  }

  const day = Number(digits.slice(0, 2))
  const month = Number(digits.slice(2, 4))
  const year = Number(digits.slice(4, 8))
  const hour = Number(digits.slice(8, 10))
  const minute = Number(digits.slice(10, 12))

  if (month < 1 || month > 12) {
    return false
  }
  if (hour > 23 || minute > 59) {
    return false
  }

  const daysInMonth = new Date(year, month, 0).getDate()
  if (day < 1 || day > daysInMonth) {
    return false
  }

  return true
}

export function maskedDatetimeToIso(value: string): string | null {
  if (!isValidMaskedDatetime(value)) {
    return null
  }

  const digits = extractDigits(value)
  const day = Number(digits.slice(0, 2))
  const month = Number(digits.slice(2, 4))
  const year = Number(digits.slice(4, 8))
  const hour = Number(digits.slice(8, 10))
  const minute = Number(digits.slice(10, 12))

  return new Date(year, month - 1, day, hour, minute, 0, 0).toISOString()
}

export function parsePositiveInt(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed || !/^\d+$/.test(trimmed)) {
    return null
  }
  const parsed = Number(trimmed)
  return parsed > 0 ? parsed : null
}

export function computeTransferToAmount(
  fromCurrency: string,
  toCurrency: string,
  amount: number,
  rate: number,
): number {
  if (fromCurrency === toCurrency) {
    return amount
  }
  if (fromCurrency === 'UZS' && toCurrency === 'USD') {
    return Math.round(amount / rate)
  }
  if (fromCurrency === 'USD' && toCurrency === 'UZS') {
    return Math.round(amount * rate)
  }
  return 0
}

export function formatReceiveAmount(amount: number, currency: string): string {
  return formatCurrency(amount, currency as Currency)
}
