import { describe, expect, it } from 'vitest'
import type { TFunction } from 'i18next'

import { prepareDonutSlices, prepareSubcategoryDonutSlices } from './analyticsCharts'
import { extendCategoryColorMap } from './analyticsChartsTab'

const t = ((k: string) => k) as TFunction

describe('«Другое» holds the smallest categories, not the newest (QA P3 #2)', () => {
  const ids = Array.from({ length: 10 }, (_, i) => `c${i}`)
  // c8 and c9 were created last but are the biggest
  const amounts = [50, 40, 30, 20, 10, 9, 8, 7, 1000, 900]
  const entries = ids.map((id, i) => ({
    category_id: id,
    category_name: id,
    category_translation_key: null,
    amount: amounts[i],
  }))

  it('parents: the 8 biggest are shown, the 2 smallest go to Другое', () => {
    const slices = prepareDonutSlices(entries, ids, extendCategoryColorMap(ids, []), 'Другое', t)
    const keys = slices.map((s) => s.key)
    expect(keys).toContain('c8')
    expect(keys).toContain('c9')
    expect(keys).not.toContain('c6')
    expect(keys).not.toContain('c7')
    expect(slices.find((s) => s.key === 'other')?.value).toBe(15)
    expect(slices.filter((s) => s.key !== 'other')).toHaveLength(8)
  })

  it('shown slices have different colours', () => {
    const slices = prepareDonutSlices(entries, ids, extendCategoryColorMap(ids, []), 'Другое', t)
    const colours = slices.filter((s) => s.key !== 'other').map((s) => s.color)
    expect(new Set(colours).size).toBe(colours.length)
  })

  it('subcategories: same rule', () => {
    const subs = ids.map((id, i) => ({
      subcategory_id: id,
      subcategory_name: id,
      amount: amounts[i],
      display_name: id,
    }))
    const slices = prepareSubcategoryDonutSlices(subs, ids, extendCategoryColorMap(ids, []), 'Другое')
    expect(slices.map((s) => s.key)).toEqual(expect.arrayContaining(['c8', 'c9']))
    expect(slices.find((s) => s.key === 'other')?.value).toBe(15)
  })
})
