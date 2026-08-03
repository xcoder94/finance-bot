export const MAX_COMMENT_LENGTH = 200
export const UNCATEGORIZED_CATEGORY_NAME = 'Без категории'

const TASHKENT_TZ = 'Asia/Tashkent'
const DATE_DIGIT_COUNT = 8

function extractDigits(value: string): string {
  return value.replace(/\D/g, '')
}

function formatDateDigits(digits: string): string {
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

export function formatCommentCounter(length: number): string {
  return `${length} / ${MAX_COMMENT_LENGTH}`
}

export function isCommentTooLong(comment: string): boolean {
  return comment.length > MAX_COMMENT_LENGTH
}

export function filterUncategorizedCategories<T extends { name: string }>(
  categories: T[],
): T[] {
  return categories.filter((category) => category.name !== UNCATEGORIZED_CATEGORY_NAME)
}

export function buildExpenseCategoryDisplayLabel(
  parentName: string,
  subcategoryName: string | null | undefined,
): string {
  if (subcategoryName) {
    return `${parentName} · ${subcategoryName}`
  }
  return parentName
}

export function walletCurrencySuffix(currency: string): string {
  return currency === 'USD' ? '$' : 'сум'
}

export function resolveDefaultWalletId(
  wallets: { id: string }[],
  defaultWalletId: string | null | undefined,
): string {
  if (defaultWalletId && wallets.some((wallet) => wallet.id === defaultWalletId)) {
    return defaultWalletId
  }
  return wallets[0]?.id ?? ''
}

export function nowMaskedDateInTashkent(): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: TASHKENT_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())

  const day = parts.find((part) => part.type === 'day')?.value ?? '01'
  const month = parts.find((part) => part.type === 'month')?.value ?? '01'
  const year = parts.find((part) => part.type === 'year')?.value ?? '2026'

  return formatDateDigits(`${day}${month}${year}`)
}

export function maskedDateToTashkentIso(value: string): string | null {
  if (!isValidMaskedDate(value)) {
    return null
  }

  const digits = extractDigits(value)
  const day = digits.slice(0, 2)
  const month = digits.slice(2, 4)
  const year = digits.slice(4, 8)

  return `${year}-${month}-${day}T12:00:00.000+05:00`
}

export function isoToMaskedDateInTashkent(iso: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: TASHKENT_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(iso))

  const day = parts.find((part) => part.type === 'day')?.value ?? '01'
  const month = parts.find((part) => part.type === 'month')?.value ?? '01'
  const year = parts.find((part) => part.type === 'year')?.value ?? '2026'

  return formatDateDigits(`${day}${month}${year}`)
}

export function isTransferCrossCurrency(
  sourceCurrency: string | null | undefined,
  destCurrency: string | null | undefined,
): boolean {
  return Boolean(sourceCurrency && destCurrency && sourceCurrency !== destCurrency)
}

export function shouldShowTransferRateField(
  sourceCurrency: string | null | undefined,
  destCurrency: string | null | undefined,
): boolean {
  return isTransferCrossCurrency(sourceCurrency, destCurrency)
}

function formatTransferSideAmount(amount: number, currency: string): string {
  const formatted = amount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
  if (currency === 'USD') {
    return `${formatted} $`
  }
  return `${formatted} сум`
}

export function formatTransferResultLine(
  fromAmount: number,
  fromCurrency: string,
  toAmount: number,
  toCurrency: string,
): string {
  return `${formatTransferSideAmount(fromAmount, fromCurrency)} → ${formatTransferSideAmount(toAmount, toCurrency)}`
}

export function transferRateFieldSuffix(): string {
  return 'сум за $1'
}

export function buildEditSheetTitle(label: string): string {
  return `Запись · ${label}`
}

export function resolveEditSheetLabel(
  comment: string | null | undefined,
  fallbackLabel: string,
): string {
  const trimmed = comment?.trim()
  return trimmed || fallbackLabel
}

export function pickAlternateWalletId(
  wallets: { id: string }[],
  excludedWalletId: string,
): string {
  const alternative = wallets.find((wallet) => wallet.id !== excludedWalletId)
  return alternative?.id ?? ''
}
