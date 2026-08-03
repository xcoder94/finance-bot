import type { HistoryCategoryFilter } from './analyticsDrill'

export function buildAnalyticsHistoryFetchKey(
  rangeKey: string,
  historyCategoryFilter: HistoryCategoryFilter | null,
): string {
  const categoryId = historyCategoryFilter?.id ?? ''
  return `${rangeKey}|${categoryId}`
}

export function getAnalyticsHistoryExpenseCategoryId(
  historyCategoryFilter: HistoryCategoryFilter | null,
): string | undefined {
  return historyCategoryFilter?.id
}
