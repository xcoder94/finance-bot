import { type Currency, formatCurrency } from './formatCurrency'

export const MAX_AMOUNT_DIGITS = 10

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
