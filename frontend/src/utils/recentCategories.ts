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
