export const CHART_CATEGORY_COLORS = [
  'var(--app-category-color-1)',
  'var(--app-category-color-2)',
  'var(--app-category-color-3)',
  'var(--app-category-color-4)',
  'var(--app-category-color-5)',
  'var(--app-category-color-6)',
  'var(--app-category-color-7)',
  'var(--app-category-color-8)',
] as const

export const OTHER_CATEGORY_COLOR_INDEX = 8
export const UNCATEGORIZED_COLOR = 'var(--app-category-color-neutral)'

export function mergeStoredCategoryColorIndices(
  categories: Array<{ id: string; color_index?: number }>,
  amounts: Array<{ color_index?: number; [key: string]: string | number | boolean | null | undefined }>,
  amountIdKey: string,
): Map<string, number> {
  const map = new Map<string, number>()

  for (const category of categories) {
    if (category.color_index !== undefined) {
      map.set(category.id, category.color_index)
    }
  }

  for (const entry of amounts) {
    const id = entry[amountIdKey]
    if (typeof id === 'string' && entry.color_index !== undefined) {
      map.set(id, entry.color_index)
    }
  }

  return map
}

export function buildCategoryColorIndexMap(
  categoryIdsInOrder: string[],
  storedColorIndexById?: Map<string, number>,
): Map<string, number> {
  const map = new Map<string, number>()
  for (let index = 0; index < categoryIdsInOrder.length; index += 1) {
    const categoryId = categoryIdsInOrder[index]
    const stored = storedColorIndexById?.get(categoryId)
    const colorIndex =
      stored !== undefined && stored >= 1 && stored <= OTHER_CATEGORY_COLOR_INDEX
        ? stored
        : index < 8
          ? index + 1
          : OTHER_CATEGORY_COLOR_INDEX
    map.set(categoryId, colorIndex)
  }
  return map
}

export type ColorSiblingInput = {
  id: string
  color_index?: number
  parent_id?: string | null
}

/**
 * Effective colour index per category. Siblings (same parent_id; null = top level) are walked in
 * list order over the FULL category list: the stored index is kept unless an earlier sibling
 * already took it, otherwise the smallest free palette index is used (cycling when exhausted).
 * Nothing is written back to the API.
 */
export function resolveEffectiveColorIndices(
  categories: ColorSiblingInput[],
): Map<string, number> {
  const groups = new Map<string, ColorSiblingInput[]>()
  for (const category of categories) {
    const key = category.parent_id ?? ''
    const group = groups.get(key)
    if (group) {
      group.push(category)
    } else {
      groups.set(key, [category])
    }
  }

  const result = new Map<string, number>()
  for (const group of groups.values()) {
    const used = new Set<number>()
    group.forEach((category, position) => {
      const stored = category.color_index
      let index: number
      if (
        stored !== undefined &&
        stored >= 1 &&
        stored <= CHART_CATEGORY_COLORS.length &&
        !used.has(stored)
      ) {
        index = stored
      } else {
        let free = 0
        for (let candidate = 1; candidate <= CHART_CATEGORY_COLORS.length; candidate += 1) {
          if (!used.has(candidate)) {
            free = candidate
            break
          }
        }
        index = free || (position % CHART_CATEGORY_COLORS.length) + 1
      }
      used.add(index)
      result.set(category.id, index)
    })
  }
  return result
}

export function getColorByIndex(colorIndex: number): string {
  const clamped = Math.min(Math.max(colorIndex, 1), OTHER_CATEGORY_COLOR_INDEX)
  return CHART_CATEGORY_COLORS[clamped - 1]
}

export function stableColorIndexFromCategoryId(categoryId: string): number {
  let hash = 0
  for (let index = 0; index < categoryId.length; index += 1) {
    hash = (hash * 31 + categoryId.charCodeAt(index)) >>> 0
  }
  return (hash % 8) + 1
}

export function getCategoryColor(categoryId: string, colorMap: Map<string, number>): string {
  const colorIndex = colorMap.get(categoryId) ?? stableColorIndexFromCategoryId(categoryId)
  return getColorByIndex(colorIndex)
}
