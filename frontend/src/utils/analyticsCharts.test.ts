import { describe, expect, it } from 'vitest'
import type { TFunction } from 'i18next'

import { prepareDonutSlices } from './analyticsCharts'
import { extendCategoryColorMap, mergeCategoryIds } from './analyticsChartsTab'
import {
  getColorByIndex,
  OTHER_CATEGORY_COLOR_INDEX,
  stableColorIndexFromCategoryId,
} from './chartColors'

describe('mergeCategoryIds', () => {
  it('appends additional ids not already in the ordered list', () => {
    expect(mergeCategoryIds(['a', 'b'], ['c', 'b'])).toEqual(['a', 'b', 'c'])
  })
})

describe('stableColorIndexFromCategoryId', () => {
  it('returns a stable color index between 1 and 8', () => {
    const categoryId = '6ba7b810-9dad-11d1-80b4-00c04fd430c8'
    expect(stableColorIndexFromCategoryId(categoryId)).toBe(
      stableColorIndexFromCategoryId(categoryId),
    )
    expect(stableColorIndexFromCategoryId(categoryId)).toBeGreaterThanOrEqual(1)
    expect(stableColorIndexFromCategoryId(categoryId)).toBeLessThanOrEqual(8)
  })
})

describe('prepareDonutSlices soft-deleted categories', () => {
  it('shows a soft-deleted category as its own slice with the API name', () => {
    const deletedId = '6ba7b811-9dad-11d1-80b4-00c04fd430c8'
    const activeId = '6ba7b812-9dad-11d1-80b4-00c04fd430c8'
    const orderedIds = mergeCategoryIds([activeId], [deletedId])
    const colorMap = extendCategoryColorMap([activeId], [deletedId])
    const slices = prepareDonutSlices(
      [{ category_id: deletedId, category_name: 'Old Food', category_translation_key: null, amount: 500 }],
      orderedIds,
      colorMap,
      'Другое',
      ((key: string) => key) as TFunction,
    )

    expect(slices).toHaveLength(1)
    expect(slices[0]).toMatchObject({
      key: deletedId,
      name: 'Old Food',
      value: 500,
    })
    expect(slices[0].color).not.toBe(getColorByIndex(OTHER_CATEGORY_COLOR_INDEX))
  })
})
