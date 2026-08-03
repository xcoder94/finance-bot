import { describe, expect, it } from 'vitest'

import {
  buildCategoryColorIndexMap,
  getColorByIndex,
} from './chartColors'

describe('buildCategoryColorIndexMap', () => {
  it('prefers stored color_index over list position', () => {
    const map = buildCategoryColorIndexMap(
      ['cat-a', 'cat-b', 'cat-c'],
      new Map([
        ['cat-a', 3],
        ['cat-b', 7],
      ]),
    )

    expect(map.get('cat-a')).toBe(3)
    expect(map.get('cat-b')).toBe(7)
    expect(map.get('cat-c')).toBe(3)
  })

  it('uses list position when stored color_index is missing', () => {
    const map = buildCategoryColorIndexMap(['cat-a', 'cat-b'])
    expect(map.get('cat-a')).toBe(1)
    expect(map.get('cat-b')).toBe(2)
  })

  it('resolves chart color from stored index', () => {
    const map = buildCategoryColorIndexMap(['cat-a'], new Map([['cat-a', 5]]))
    expect(getColorByIndex(map.get('cat-a')!)).toBe('var(--app-category-color-5)')
  })
})
