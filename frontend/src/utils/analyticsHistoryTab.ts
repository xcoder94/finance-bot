import type { HistoryCategoryFilter } from './analyticsDrill'

export function buildAnalyticsHistoryFetchKey(
  rangeKey: string,
  historyCategoryFilter: HistoryCategoryFilter | null,
): string {
  const categoryId = historyCategoryFilter?.uncategorized
    ? 'uncategorized'
    : (historyCategoryFilter?.id ?? '')
  return `${rangeKey}|${categoryId}`
}

export function getAnalyticsHistoryExpenseCategoryId(
  historyCategoryFilter: HistoryCategoryFilter | null,
): string | undefined {
  if (historyCategoryFilter?.uncategorized) {
    return undefined
  }
  return historyCategoryFilter?.id
}

export function isAnalyticsHistoryUncategorized(
  historyCategoryFilter: HistoryCategoryFilter | null,
): boolean {
  return historyCategoryFilter?.uncategorized === true
}

/** PRD 17 #8: the plain History tab lists all currencies; the currency is sent only for a drill from a chart. */
export function historyCurrencyParam(
  historyCategoryFilter: HistoryCategoryFilter | null,
  chartCurrency: string,
): string | undefined {
  return historyCategoryFilter ? chartCurrency : undefined
}

/** Charts count shared wallets only; a category-filtered list must match them. */
export function excludePersonalWalletRows<
  T extends { wallet_id: string; to_wallet_id: string | null },
>(items: T[], personalWalletIds: ReadonlySet<string>): T[] {
  if (personalWalletIds.size === 0) {
    return items
  }
  return items.filter(
    (item) =>
      !personalWalletIds.has(item.wallet_id) &&
      !(item.to_wallet_id !== null && personalWalletIds.has(item.to_wallet_id)),
  )
}
