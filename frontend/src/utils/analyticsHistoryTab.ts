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

/** With a filter the list is not drawn until the wallet list is known (no personal rows flash in). */
export function historyListStatus<S extends string>(
  status: S,
  filterActive: boolean,
  walletsReady: boolean,
): S | 'loading' {
  return filterActive && !walletsReady && status === 'success' ? 'loading' : status
}

/**
 * Quiet refresh on return: re-read everything already shown (offset 0 .. loaded) in as few
 * requests as the API allows, so the list keeps its length and the scroll position.
 */
export function planSilentHistoryRefresh(
  loaded: number,
  pageSize = 50,
  maxLimit = 500,
): Array<{ offset: number; limit: number }> {
  const want = Math.max(pageSize, loaded)
  const plan: Array<{ offset: number; limit: number }> = []
  for (let offset = 0; offset < want; offset += maxLimit) {
    plan.push({ offset, limit: Math.min(maxLimit, want - offset) })
  }
  return plan
}

/** The list is "the same list" while only the data epoch moved: then it refreshes without clearing. */
export function isQuietHistoryRefresh(
  previousIdentity: string | null,
  identity: string,
  hasItems: boolean,
): boolean {
  return hasItems && previousIdentity === identity
}
