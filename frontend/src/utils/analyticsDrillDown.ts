import {
  fetchExpensesBySubcategory,
} from '../api/analytics'
import type { ExpenseCategory } from '../api/transactions'
import type { TFunction } from 'i18next'
import {
  buildSubcategoryDisplayEntries,
  getOrderedSubcategoryIdsForOther,
  getOrderedSubcategoryIdsForParent,
  mergeOtherSubcategoryEntries,
  type ParentCategoryCard,
  type SubcategoryDisplayEntry,
  type SubcategoryDrillDownState,
} from './analyticsCharts'
import { OTHER_CATEGORY_KEY } from './analyticsConstants'
import { buildCategoryColorIndexMap } from './chartColors'

export async function fetchSubcategoryEntriesForCard(
  card: ParentCategoryCard,
  currency: string,
  dateFrom: string,
  dateTo: string,
  parentNameById: Map<string, string>,
  t: TFunction,
  displayNameById?: Map<string, string>,
): Promise<SubcategoryDisplayEntry[]> {
  if (card.key === OTHER_CATEGORY_KEY) {
    const groupedItems = await Promise.all(
      card.parentIds.map(async (parentId) => ({
        parentId,
        items: await fetchExpensesBySubcategory(parentId, currency, dateFrom, dateTo),
      })),
    )
    return mergeOtherSubcategoryEntries(groupedItems, parentNameById, t, displayNameById)
  }

  const items = await fetchExpensesBySubcategory(card.parentIds[0], currency, dateFrom, dateTo)
  return buildSubcategoryDisplayEntries(
    items,
    false,
    parentNameById,
    t,
    card.parentIds[0],
    displayNameById,
  )
}

export function buildDrillDownStateForCard(
  card: ParentCategoryCard,
  entries: SubcategoryDisplayEntry[],
  expenseCategories: ExpenseCategory[],
  expenseParentIds: string[],
): SubcategoryDrillDownState {
  const isOther = card.key === OTHER_CATEGORY_KEY
  const orderedSubcategoryIds = isOther
    ? getOrderedSubcategoryIdsForOther(expenseParentIds.slice(8), expenseCategories)
    : getOrderedSubcategoryIdsForParent(card.parentIds[0], expenseCategories)

  return {
    categoryKey: card.key,
    categoryName: card.name,
    isOther,
    entries,
    orderedSubcategoryIds,
    colorMap: buildCategoryColorIndexMap(orderedSubcategoryIds),
  }
}

export type CardSubcategoryData = {
  card: ParentCategoryCard
  drillDown: SubcategoryDrillDownState
}

export async function fetchCardSubcategoryData(
  card: ParentCategoryCard,
  currency: string,
  dateFrom: string,
  dateTo: string,
  expenseCategories: ExpenseCategory[],
  expenseParentIds: string[],
  parentNameById: Map<string, string>,
  t: TFunction,
  displayNameById?: Map<string, string>,
): Promise<CardSubcategoryData> {
  const entries = await fetchSubcategoryEntriesForCard(
    card,
    currency,
    dateFrom,
    dateTo,
    parentNameById,
    t,
    displayNameById,
  )

  return {
    card,
    drillDown: buildDrillDownStateForCard(card, entries, expenseCategories, expenseParentIds),
  }
}

export function findParentCategoryCard(
  cards: ParentCategoryCard[],
  categoryKey: string,
): ParentCategoryCard | undefined {
  return cards.find((card) => card.key === categoryKey)
}
