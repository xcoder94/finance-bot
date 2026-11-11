import { describe, expect, it } from 'vitest'

import {
  MAX_RECENT_CATEGORIES,
  mergeRecentIds,
  readRecentCategories,
  recentIdsFromHistory,
  recentCategoriesKey,
  recordRecentCategory,
  resolveRecentChips,
  type RecentStorage,
} from './recentCategories'

function memoryStorage(): RecentStorage & { data: Map<string, string> } {
  const data = new Map<string, string>()
  return {
    data,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
  }
}

describe('recent categories storage', () => {
  it('returns newest first', () => {
    const s = memoryStorage()
    recordRecentCategory('b1', 'expense', 'c1', s)
    recordRecentCategory('b1', 'expense', 'c2', s)
    recordRecentCategory('b1', 'expense', 'c3', s)
    expect(readRecentCategories('b1', 'expense', s)).toEqual(['c3', 'c2', 'c1'])
  })

  it('moves a repeated category to the front without duplicating it', () => {
    const s = memoryStorage()
    for (const id of ['c1', 'c2', 'c3', 'c1']) {
      recordRecentCategory('b1', 'expense', id, s)
    }
    expect(readRecentCategories('b1', 'expense', s)).toEqual(['c1', 'c3', 'c2'])
  })

  it('keeps at most 5', () => {
    const s = memoryStorage()
    for (let i = 1; i <= 8; i += 1) {
      recordRecentCategory('b1', 'expense', `c${i}`, s)
    }
    const list = readRecentCategories('b1', 'expense', s)
    expect(MAX_RECENT_CATEGORIES).toBe(5)
    expect(list).toEqual(['c8', 'c7', 'c6', 'c5', 'c4'])
  })

  it('is separate per budget and per type', () => {
    const s = memoryStorage()
    recordRecentCategory('b1', 'expense', 'c1', s)
    recordRecentCategory('b2', 'expense', 'c2', s)
    recordRecentCategory('b1', 'income', 'i1', s)
    expect(readRecentCategories('b1', 'expense', s)).toEqual(['c1'])
    expect(readRecentCategories('b2', 'expense', s)).toEqual(['c2'])
    expect(readRecentCategories('b1', 'income', s)).toEqual(['i1'])
    expect(recentCategoriesKey('b1', 'expense')).not.toBe(recentCategoriesKey('b1', 'income'))
  })

  it('survives corrupted storage and a missing budget', () => {
    const s = memoryStorage()
    s.setItem(recentCategoriesKey('b1', 'expense'), '{not json')
    expect(readRecentCategories('b1', 'expense', s)).toEqual([])
    recordRecentCategory('', 'expense', 'c1', s)
    expect(readRecentCategories('', 'expense', s)).toEqual([])
  })

  it('does not throw when storage is unavailable', () => {
    const broken: RecentStorage = {
      getItem: () => {
        throw new Error('denied')
      },
      setItem: () => {
        throw new Error('denied')
      },
    }
    expect(readRecentCategories('b1', 'expense', broken)).toEqual([])
    expect(() => recordRecentCategory('b1', 'expense', 'c1', broken)).not.toThrow()
  })
})

describe('resolveRecentChips', () => {
  const categories = [
    { id: 'p1', name: 'Еда', parent_id: null },
    { id: 's1', name: 'Кафе', parent_id: 'p1' },
    { id: 'p2', name: 'Дом', parent_id: null },
  ]
  const label = (c: { name: string }, parent: { name: string } | null) =>
    parent ? `${parent.name} · ${c.name}` : c.name

  it('labels a parent by name and a subcategory as Parent · Sub', () => {
    expect(resolveRecentChips(['s1', 'p2'], categories, label)).toEqual([
      { id: 's1', label: 'Еда · Кафе' },
      { id: 'p2', label: 'Дом' },
    ])
  })

  it('drops categories that no longer exist, keeping order', () => {
    expect(resolveRecentChips(['gone', 'p2', 'also-gone', 'p1'], categories, label)).toEqual([
      { id: 'p2', label: 'Дом' },
      { id: 'p1', label: 'Еда' },
    ])
  })

  it('drops the uncategorized bucket', () => {
    const withBucket = [...categories, { id: 'u', name: 'Без категории', parent_id: null }]
    expect(resolveRecentChips(['u', 'p1'], withBucket, label)).toEqual([{ id: 'p1', label: 'Еда' }])
  })
})

describe('recent category ids from the server history (bot entries count too)', () => {
  const categories = [
    { id: 'food', name: 'Еда', translation_key: 'food', parent_id: null },
    { id: 'cafe', name: 'Кафе', translation_key: null, parent_id: 'food' },
    { id: 'home', name: 'Дом', translation_key: null, parent_id: null },
    { id: 'salary', name: 'Зарплата', translation_key: null },
  ]
  const item = (over: Record<string, unknown>) => ({
    type: 'expense',
    expense_category_name: null,
    expense_category_translation_key: null,
    expense_subcategory_name: null,
    expense_subcategory_translation_key: null,
    income_category_name: null,
    income_category_translation_key: null,
    ...over,
  })

  it('takes the subcategory when there is one, the parent otherwise, newest first, deduped', () => {
    const items = [
      item({ expense_category_name: 'Еда', expense_category_translation_key: 'food', expense_subcategory_name: 'Кафе' }),
      item({ expense_category_name: 'Дом' }),
      item({ expense_category_name: 'Еда', expense_category_translation_key: 'food', expense_subcategory_name: 'Кафе' }),
    ]
    expect(recentIdsFromHistory(items, categories, 'expense')).toEqual(['cafe', 'home'])
  })

  it('ignores other types, transfers and unknown categories; income reads its own field', () => {
    const items = [
      item({ type: 'transfer' }),
      item({ type: 'income', income_category_name: 'Зарплата' }),
      item({ expense_category_name: 'Удалённая' }),
    ]
    expect(recentIdsFromHistory(items, categories, 'expense')).toEqual([])
    expect(recentIdsFromHistory(items, categories, 'income')).toEqual(['salary'])
  })

  it('keeps at most 5', () => {
    const many = Array.from({ length: 7 }, (_, i) => ({ id: `c${i}`, name: `N${i}`, translation_key: null, parent_id: null }))
    const items = many.map((c) => item({ expense_category_name: c.name }))
    expect(recentIdsFromHistory(items, many, 'expense')).toHaveLength(MAX_RECENT_CATEGORIES)
  })

  it('a parent-only operation arrives with the parent in the subcategory field (U2.3)', () => {
    const items = [
      item({ expense_category_name: null, expense_subcategory_name: 'Дом' }),
      item({ expense_category_name: null, expense_subcategory_name: 'Еда', expense_subcategory_translation_key: 'food' }),
    ]
    expect(recentIdsFromHistory(items, categories, 'expense')).toEqual(['home', 'food'])
  })

  it('a name in the subcategory field that is not a top-level category is skipped', () => {
    const items = [item({ expense_category_name: null, expense_subcategory_name: 'Кафе' })]
    expect(recentIdsFromHistory(items, categories, 'expense')).toEqual([])
  })

  it('local and server lists are united: local (just saved) first, no duplicates, max 5', () => {
    expect(mergeRecentIds(['a', 'b'], ['x', 'a'])).toEqual(['x', 'a', 'b'])
    expect(mergeRecentIds([], ['x'])).toEqual(['x'])
    expect(mergeRecentIds(['x'], [])).toEqual(['x'])
    expect(mergeRecentIds(['s1', 's2', 's3'], ['l1', 'l2', 'l3'])).toEqual(['l1', 'l2', 'l3', 's1', 's2'])
  })

  it('6 saves in the app that the server list only partly knows still give 5 chips', () => {
    const local = ['f', 'e', 'd', 'c', 'b']
    expect(mergeRecentIds(['taxi'], local)).toHaveLength(MAX_RECENT_CATEGORIES)
  })
})
