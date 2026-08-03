import { OTHER_CATEGORY_KEY } from './analyticsConstants'
import { getColorByIndex } from './chartColors'

export type HistoryCategoryFilter = {
  id: string
  name: string
  color: string
}

export type ClearHistoryFilterOptions = {
  returnToDrill?: boolean
}

export function isOtherCategoryKey(key: string): boolean {
  return key === OTHER_CATEGORY_KEY
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
