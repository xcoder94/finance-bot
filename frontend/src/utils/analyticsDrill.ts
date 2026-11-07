import { OTHER_CATEGORY_KEY, UNCATEGORIZED_KEY } from './analyticsConstants'
import { UNCATEGORIZED_COLOR, getColorByIndex } from './chartColors'

export type HistoryCategoryFilter = {
  id: string
  name: string
  color: string
  uncategorized?: boolean
}

export type ClearHistoryFilterOptions = {
  returnToDrill?: boolean
}

export function isOtherCategoryKey(key: string): boolean {
  return key === OTHER_CATEGORY_KEY
}

export function isUncategorizedKey(key: string): boolean {
  return key === UNCATEGORIZED_KEY
}

export function historyFilterForUncategorized(name: string): HistoryCategoryFilter {
  return {
    id: UNCATEGORIZED_KEY,
    name,
    color: UNCATEGORIZED_COLOR,
    uncategorized: true,
  }
}

export function shouldIgnoreDonutTap(key: string): boolean {
  return isOtherCategoryKey(key)
}

export function historyFilterAfterSubcategoryTap(
  subId: string,
  name: string,
  colorIndex: number,
): HistoryCategoryFilter {
  return {
    id: subId,
    name,
    color: getColorByIndex(colorIndex),
  }
}

export function clearHistoryFilter(_options?: ClearHistoryFilterOptions): null {
  return null
}
