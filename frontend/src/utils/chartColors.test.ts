import { describe, expect, it } from 'vitest'

import {
  buildCategoryColorIndexMap,
  resolveEffectiveColorIndices,
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

describe('resolveEffectiveColorIndices (B3)', () => {
  const mk = (id: string, color_index: number, parent_id: string | null = null) => ({
    id,
    color_index,
    parent_id,
  })

  it('6 of 7 parents stored at 1 -> 7 distinct colours', () => {
    const cats = [
      mk('p1', 1), mk('p2', 1), mk('p3', 1), mk('p4', 1),
      mk('p5', 5), mk('p6', 1), mk('p7', 1),
    ]
    const map = resolveEffectiveColorIndices(cats)
    const values = cats.map((c) => map.get(c.id))
    expect(new Set(values).size).toBe(7)
    expect(map.get('p1')).toBe(1)
    expect(map.get('p5')).toBe(5)
  })

  it('4 subcategories of one parent stored at 1 -> 4 distinct; groups are independent', () => {
    const cats = [
      mk('home', 1),
      mk('s1', 1, 'home'), mk('s2', 1, 'home'), mk('s3', 1, 'home'), mk('s4', 1, 'home'),
      mk('food', 2),
      mk('f1', 1, 'food'),
    ]
    const map = resolveEffectiveColorIndices(cats)
    expect(new Set(['s1', 's2', 's3', 's4'].map((id) => map.get(id))).size).toBe(4)
    expect(map.get('f1')).toBe(1)
    expect(map.get('home')).toBe(1)
  })

  it('colour does not depend on which categories have spending', () => {
    const cats = [mk('a', 1), mk('b', 1), mk('c', 1)]
    const first = resolveEffectiveColorIndices(cats)
    const second = resolveEffectiveColorIndices(cats)
    expect(first.get('c')).toBe(second.get('c'))
    expect(first.get('c')).toBe(3)
  })

  it('cycles the palette past 8 siblings', () => {
    const cats = Array.from({ length: 10 }, (_, i) => mk(`c${i}`, 1))
    const map = resolveEffectiveColorIndices(cats)
    for (const c of cats) {
      expect(map.get(c.id)).toBeGreaterThanOrEqual(1)
      expect(map.get(c.id)).toBeLessThanOrEqual(8)
    }
    expect(new Set(cats.slice(0, 8).map((c) => map.get(c.id))).size).toBe(8)
  })
})
