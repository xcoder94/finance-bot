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

/** Display-side guard: a page may still carry other-currency rows if the server ignores `currency`. */
export function filterHistoryByCurrency<T extends { currency: string }>(
  items: T[],
  currency: string,
): T[] {
  return items.filter((item) => item.currency === currency)
}
