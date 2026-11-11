import { UNCATEGORIZED_CATEGORY_NAME } from './transactionFormFields'

export const MAX_RECENT_CATEGORIES = 5

export type RecentType = 'expense' | 'income'

export type RecentStorage = Pick<Storage, 'getItem' | 'setItem'>

export function recentCategoriesKey(budgetId: string, type: RecentType): string {
  return `recent-categories:${budgetId}:${type}`
}

function defaultStorage(): RecentStorage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}

export function readRecentCategories(
  budgetId: string,
  type: RecentType,
  storage: RecentStorage | null = defaultStorage(),
): string[] {
  if (!budgetId || !storage) {
    return []
  }
  try {
    const parsed: unknown = JSON.parse(storage.getItem(recentCategoriesKey(budgetId, type)) ?? '[]')
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed.filter((id): id is string => typeof id === 'string').slice(0, MAX_RECENT_CATEGORIES)
  } catch {
    return []
  }
}

/** Call after a successful save: puts the category first, dedupes, keeps 5. */
export function recordRecentCategory(
  budgetId: string,
  type: RecentType,
  categoryId: string,
  storage: RecentStorage | null = defaultStorage(),
): void {
  if (!budgetId || !categoryId || !storage) {
    return
  }
  try {
    const next = [
      categoryId,
      ...readRecentCategories(budgetId, type, storage).filter((id) => id !== categoryId),
    ].slice(0, MAX_RECENT_CATEGORIES)
    storage.setItem(recentCategoriesKey(budgetId, type), JSON.stringify(next))
  } catch {
    // storage full or denied: recents are a convenience, never block a save
  }
}

type RecentCategory = { id: string; name: string; parent_id?: string | null }

export type RecentChip = { id: string; label: string }

/** Maps stored ids to chips; ids not in the current category list (deleted) are dropped. */
export function resolveRecentChips<C extends RecentCategory>(
  ids: string[],
  categories: C[],
  label: (category: C, parent: C | null) => string,
): RecentChip[] {
  const byId = new Map(categories.map((category) => [category.id, category]))
  const chips: RecentChip[] = []
  for (const id of ids) {
    const category = byId.get(id)
    if (!category || category.name === UNCATEGORIZED_CATEGORY_NAME) {
      continue
    }
    const parent = category.parent_id ? (byId.get(category.parent_id) ?? null) : null
    if (category.parent_id && !parent) {
      continue
    }
    chips.push({ id, label: label(category, parent) })
  }
  return chips.slice(0, MAX_RECENT_CATEGORIES)
}

type RecentSourceCategory = { id: string; name: string; translation_key?: string | null; parent_id?: string | null }

type RecentHistoryItem = {
  type: string
  expense_category_name: string | null
  expense_category_translation_key: string | null
  expense_subcategory_name: string | null
  expense_subcategory_translation_key: string | null
  income_category_name: string | null
  income_category_translation_key: string | null
}

function sameCategory(
  category: RecentSourceCategory,
  name: string | null,
  translationKey: string | null,
): boolean {
  if (translationKey && category.translation_key) {
    return category.translation_key === translationKey
  }
  return name !== null && category.name === name
}

/**
 * Recent category ids from the budget's latest operations (newest first), so entries made through
 * the bot count too. The history API returns names, not ids, so categories are matched by
 * translation key / name; the subcategory wins over its parent. Unknown (deleted) names are skipped.
 */
export function recentIdsFromHistory<C extends RecentSourceCategory>(
  items: RecentHistoryItem[],
  categories: C[],
  type: RecentType,
): string[] {
  const ids: string[] = []
  for (const item of items) {
    if (item.type !== type) {
      continue
    }
    let match: C | undefined
    if (type === 'income') {
      match = categories.find((c) =>
        sameCategory(c, item.income_category_name, item.income_category_translation_key),
      )
    } else {
      const parent = categories.find(
        (c) =>
          !c.parent_id &&
          sameCategory(c, item.expense_category_name, item.expense_category_translation_key),
      )
      if (parent && item.expense_subcategory_name) {
        match = categories.find(
          (c) =>
            c.parent_id === parent.id &&
            sameCategory(c, item.expense_subcategory_name, item.expense_subcategory_translation_key),
        )
      } else {
        match = parent
      }
    }
    if (match && !ids.includes(match.id)) {
      ids.push(match.id)
      if (ids.length === MAX_RECENT_CATEGORIES) {
        break
      }
    }
  }
  return ids
}

/** Server answer wins; the local list only stands in until it arrives (or when the server has none). */
export function mergeRecentIds(serverIds: string[], localIds: string[]): string[] {
  return serverIds.length > 0 ? serverIds : localIds
}
