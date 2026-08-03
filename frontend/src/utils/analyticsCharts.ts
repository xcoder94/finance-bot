import type { TFunction } from 'i18next'

import type { CategoryAmount, SubcategoryAmount, TrendEntry } from '../api/analytics'
import { OTHER_CATEGORY_KEY } from './analyticsConstants'
import {
  resolveCategoryAmountDisplayName,
  resolveSubcategoryAmountDisplayName,
} from './getDisplayName'
import {
  getCategoryColor,
  getColorByIndex,
  OTHER_CATEGORY_COLOR_INDEX,
} from './chartColors'

export type DonutSlice = {
  key: string
  name: string
  value: number
  color: string
}

export type ParentCategoryCard = {
  key: string
  name: string
  amount: number
  parentIds: string[]
}

export type SubcategoryDisplayEntry = {
  subcategory_id: string
  subcategory_name: string
  amount: number
  parent_id?: string
  parent_name?: string
  display_name: string
}

export type SubcategoryDrillDownState = {
  categoryKey: string
  categoryName: string
  isOther: boolean
  entries: SubcategoryDisplayEntry[]
  orderedSubcategoryIds: string[]
  colorMap: Map<string, number>
}

export function buildParentCategoryCards(
  entries: CategoryAmount[],
  orderedParentIds: string[],
  otherLabel: string,
  t: TFunction,
  displayNameById?: Map<string, string>,
): ParentCategoryCard[] {
  const withAmount = entries.filter((entry) => entry.amount > 0)
  const cards: ParentCategoryCard[] = []
  let otherAmount = 0
  const otherParentIds: string[] = []

  for (const entry of withAmount) {
    const orderIndex = orderedParentIds.indexOf(entry.category_id)
    if (orderIndex >= 0 && orderIndex < 8) {
      cards.push({
        key: entry.category_id,
        name: resolveCategoryAmountDisplayName(entry, displayNameById, t),
        amount: entry.amount,
        parentIds: [entry.category_id],
      })
      continue
    }

    otherAmount += entry.amount
    otherParentIds.push(entry.category_id)
  }

  if (otherAmount > 0) {
    cards.push({
      key: OTHER_CATEGORY_KEY,
      name: otherLabel,
      amount: otherAmount,
      parentIds: otherParentIds,
    })
  }

  return cards.sort((left, right) => right.amount - left.amount)
}

export function getOverflowParentIds(orderedParentIds: string[]): string[] {
  return orderedParentIds.slice(8)
}

export function getOrderedSubcategoryIdsForParent(
  parentId: string,
  expenseCategories: Array<{ id: string; parent_id: string | null }>,
): string[] {
  return expenseCategories.filter((category) => category.parent_id === parentId).map((category) => category.id)
}

export function getOrderedSubcategoryIdsForOther(
  overflowParentIds: string[],
  expenseCategories: Array<{ id: string; parent_id: string | null }>,
): string[] {
  const orderedIds: string[] = []
  for (const parentId of overflowParentIds) {
    orderedIds.push(...getOrderedSubcategoryIdsForParent(parentId, expenseCategories))
  }
  return orderedIds
}

export function prepareSubcategoryDonutSlices(
  entries: SubcategoryDisplayEntry[],
  orderedSubcategoryIds: string[],
  colorMap: Map<string, number>,
  otherLabel: string,
): DonutSlice[] {
  const withAmount = entries.filter((entry) => entry.amount > 0)
  if (withAmount.length === 0) {
    return []
  }

  const slices = new Map<string, DonutSlice>()
  let otherAmount = 0

  for (const entry of withAmount) {
    const orderIndex = orderedSubcategoryIds.indexOf(entry.subcategory_id)
    if (orderIndex >= 0 && orderIndex < 8) {
      slices.set(entry.subcategory_id, {
        key: entry.subcategory_id,
        name: entry.display_name,
        value: entry.amount,
        color: getCategoryColor(entry.subcategory_id, colorMap),
      })
      continue
    }

    otherAmount += entry.amount
  }

  const result = Array.from(slices.values())
  if (otherAmount > 0) {
    result.push({
      key: OTHER_CATEGORY_KEY,
      name: otherLabel,
      value: otherAmount,
      color: getColorByIndex(OTHER_CATEGORY_COLOR_INDEX),
    })
  }

  return result.sort((left, right) => right.value - left.value)
}

export function buildSubcategoryDisplayEntries(
  items: SubcategoryAmount[],
  isOther: boolean,
  parentNameById: Map<string, string>,
  t: TFunction,
  parentId?: string,
  displayNameById?: Map<string, string>,
): SubcategoryDisplayEntry[] {
  return items
    .filter((item) => item.amount > 0)
    .map((item) => {
      const resolvedParentName = parentId ? (parentNameById.get(parentId) ?? '—') : undefined
      const subcategoryDisplayName = resolveSubcategoryAmountDisplayName(
        item,
        displayNameById,
        t,
      )

      return {
        subcategory_id: item.subcategory_id,
        subcategory_name: item.subcategory_name,
        amount: item.amount,
        parent_id: parentId,
        parent_name: resolvedParentName,
        display_name:
          isOther && resolvedParentName
            ? `${resolvedParentName}: ${subcategoryDisplayName}`
            : subcategoryDisplayName,
      }
    })
}

export function mergeOtherSubcategoryEntries(
  groupedItems: Array<{ parentId: string; items: SubcategoryAmount[] }>,
  parentNameById: Map<string, string>,
  t: TFunction,
  displayNameById?: Map<string, string>,
): SubcategoryDisplayEntry[] {
  return groupedItems.flatMap(({ parentId, items }) =>
    buildSubcategoryDisplayEntries(items, true, parentNameById, t, parentId, displayNameById),
  )
}

export function sortSubcategoryEntriesByAmount(
  entries: SubcategoryDisplayEntry[],
): SubcategoryDisplayEntry[] {
  return [...entries].sort((left, right) => right.amount - left.amount)
}

export function prepareDonutSlices(
  entries: CategoryAmount[],
  orderedCategoryIds: string[],
  colorMap: Map<string, number>,
  otherLabel: string,
  t: TFunction,
  displayNameById?: Map<string, string>,
): DonutSlice[] {
  const withAmount = entries.filter((entry) => entry.amount > 0)
  if (withAmount.length === 0) {
    return []
  }

  const slices = new Map<string, DonutSlice>()
  let otherAmount = 0

  for (const entry of withAmount) {
    const orderIndex = orderedCategoryIds.indexOf(entry.category_id)
    if (orderIndex >= 0 && orderIndex < 8) {
      slices.set(entry.category_id, {
        key: entry.category_id,
        name: resolveCategoryAmountDisplayName(entry, displayNameById, t),
        value: entry.amount,
        color: getCategoryColor(entry.category_id, colorMap),
      })
      continue
    }

    otherAmount += entry.amount
  }

  const result = Array.from(slices.values())
  if (otherAmount > 0) {
    result.push({
      key: OTHER_CATEGORY_KEY,
      name: otherLabel,
      value: otherAmount,
      color: getColorByIndex(OTHER_CATEGORY_COLOR_INDEX),
    })
  }

  return result
}

export function countNonzeroCategories(entries: CategoryAmount[]): number {
  return entries.filter((entry) => entry.amount > 0).length
}

export function getLast12MonthKeys(referenceDate = new Date()): string[] {
  let year = referenceDate.getFullYear()
  let month = referenceDate.getMonth() + 1
  const keys: string[] = []

  for (let index = 0; index < 12; index += 1) {
    keys.push(`${year}-${String(month).padStart(2, '0')}`)
    month -= 1
    if (month === 0) {
      month = 12
      year -= 1
    }
  }

  return keys.reverse()
}

export type TrendChartRow = {
  month: string
  label: string
  income: number
  expense: number
}

export function buildTrendChartRows(
  entries: TrendEntry[],
  currency: string,
  monthKeys: string[],
  formatMonthLabel: (monthKey: string) => string,
): TrendChartRow[] {
  const byMonth = new Map<string, { income: number; expense: number }>()

  for (const entry of entries) {
    if (entry.currency !== currency) {
      continue
    }
    byMonth.set(entry.month, { income: entry.income, expense: entry.expense })
  }

  return monthKeys.map((month) => ({
    month,
    label: formatMonthLabel(month),
    income: byMonth.get(month)?.income ?? 0,
    expense: byMonth.get(month)?.expense ?? 0,
  }))
}

export function formatPercent(value: number, total: number): string {
  if (total <= 0) {
    return '0%'
  }
  return `${Math.round((value / total) * 100)}%`
}
