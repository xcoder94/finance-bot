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

export function buildCategoryColorIndexMap(categoryIdsInOrder: string[]): Map<string, number> {
  const map = new Map<string, number>()
  for (let index = 0; index < categoryIdsInOrder.length; index += 1) {
    const colorIndex = index < 8 ? index + 1 : OTHER_CATEGORY_COLOR_INDEX
    map.set(categoryIdsInOrder[index], colorIndex)
  }
  return map
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
