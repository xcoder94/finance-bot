import { describe, expect, it } from 'vitest'

import { editRouteForItem } from './editRouteForItem'

describe('editRouteForItem', () => {
  it('routes income, expense and transfer to their edit sheets', () => {
    expect(editRouteForItem({ id: 'a', type: 'income' })).toBe('/edit-income/a')
    expect(editRouteForItem({ id: 'b', type: 'expense' })).toBe('/edit-expense/b')
    expect(editRouteForItem({ id: 'c', type: 'transfer' })).toBe('/edit-transfer/c')
  })

  it('treats unknown types as transfer edit (exchange shares transfer type)', () => {
    expect(editRouteForItem({ id: 'd', type: 'exchange' })).toBe('/edit-transfer/d')
  })
})
