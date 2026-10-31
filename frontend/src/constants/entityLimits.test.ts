import { describe, expect, it } from 'vitest'

import {
  limitExpenseParents,
  limitIncomeCategories,
  limitMembers,
  limitPersonalWallets,
  limitSharedWallets,
  limitSubcategories,
} from './entityLimits'

describe('entity limit strings §19.1', () => {
  it('exports shared wallets limit verbatim', () => {
    expect(limitSharedWallets()).toBe(
      'Больше 10 общих кошельков создать нельзя. Удалите ненужный — место освободится.',
    )
  })

  it('exports personal wallets limit verbatim', () => {
    expect(limitPersonalWallets()).toBe(
      'Больше 5 личных кошельков создать нельзя. Удалите ненужный — место освободится.',
    )
  })

  it('exports expense parents limit verbatim', () => {
    expect(limitExpenseParents()).toBe(
      'Больше 8 категорий расходов создать нельзя. Удалите ненужную — место освободится.',
    )
  })

  it('exports income categories limit verbatim', () => {
    expect(limitIncomeCategories()).toBe(
      'Больше 8 категорий доходов создать нельзя. Удалите ненужную — место освободится.',
    )
  })

  it('builds subcategory limit with parent name', () => {
    expect(limitSubcategories('Еда')).toBe(
      'В категории «Еда» уже 8 подкатегорий — это предел. Удалите ненужную, чтобы добавить новую.',
    )
  })

  it('exports members limit verbatim', () => {
    expect(limitMembers()).toBe(
      'В семейном бюджете уже 4 участника — это предел.',
    )
  })
})
