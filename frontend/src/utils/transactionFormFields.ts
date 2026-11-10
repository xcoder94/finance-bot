import { t } from '../i18n/t'
import { sumUnit } from './currencyUnit'
import { groupThousands } from './groupThousands'
export const MAX_COMMENT_LENGTH = 200
export const UNCATEGORIZED_CATEGORY_NAME = 'Без категории'

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
  return currency === 'USD' ? '$' : sumUnit()
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
  const formatted = groupThousands(amount)
  if (currency === 'USD') {
    return `${formatted} $`
  }
  return `${formatted} ${sumUnit()}`
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
  return t('formSheet.rateSuffix', { unit: sumUnit() })
}

export function buildEditSheetTitle(label: string): string {
  return t('formSheet.editTitle', { label })
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
