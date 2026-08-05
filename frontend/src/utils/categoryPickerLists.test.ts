import { describe, expect, it } from 'vitest'

import {
  getExpensePickerParentCategories,
  getExpensePickerSubcategories,
} from './categoryPickerLists'

describe('category picker lists', () => {
  const activeParents = [
    { id: 'food', name: 'Еда', translation_key: null, parent_id: null, transaction_count: 0, color_index: 1, is_protected: false },
    { id: 'transport', name: 'Транспорт', translation_key: null, parent_id: null, transaction_count: 0, color_index: 2, is_protected: false },
  ]
  const activeSubs = [
    { id: 'groceries', name: 'Продукты', translation_key: null, parent_id: 'food', transaction_count: 0, color_index: 3, is_protected: false },
    { id: 'cafe', name: 'Кафе', translation_key: null, parent_id: 'food', transaction_count: 0, color_index: 4, is_protected: false },
  ]

  it('lists only categories returned by GET (soft-deleted omitted server-side)', () => {
    const apiResponse = [...activeParents, ...activeSubs]

    expect(getExpensePickerParentCategories(apiResponse).map((category) => category.id)).toEqual([
      'food',
      'transport',
    ])
    expect(
      getExpensePickerSubcategories(apiResponse, 'food').map((category) => category.id),
    ).toEqual(['groceries', 'cafe'])
    expect(
      getExpensePickerParentCategories(apiResponse).some((category) => category.id === 'deleted'),
    ).toBe(false)
  })
})
