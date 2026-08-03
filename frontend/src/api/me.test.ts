import { describe, expect, it } from 'vitest'

import { mapMeResponse } from './me'

describe('mapMeResponse', () => {
  it('maps budget_name to budgetName for the Home heading', () => {
    const user = mapMeResponse({
      id: 'user-1',
      telegram_id: 42,
      family_budget_id: 'family-1',
      role: 'owner',
      first_name: 'Alex',
      username: 'alex',
      language: 'ru',
      budget_name: 'Семейный бюджет',
      member_count: 3,
      default_wallet_id: null,
    })

    expect(user.budgetName).toBe('Семейный бюджет')
    expect(user.budgetName).not.toBe('Мои финансы')
  })

  it('maps default_wallet_id to defaultWalletId', () => {
    const user = mapMeResponse({
      id: 'user-1',
      telegram_id: 42,
      family_budget_id: 'family-1',
      role: 'owner',
      first_name: 'Alex',
      username: 'alex',
      language: 'ru',
      budget_name: 'Семейный бюджет',
      member_count: 1,
      default_wallet_id: 'wallet-abc',
    })

    expect(user.defaultWalletId).toBe('wallet-abc')
  })

  it('maps null default_wallet_id to null defaultWalletId', () => {
    const user = mapMeResponse({
      id: 'user-1',
      telegram_id: 42,
      family_budget_id: 'family-1',
      role: 'owner',
      first_name: null,
      username: null,
      language: 'ru',
      budget_name: 'Семейный бюджет',
      member_count: 1,
      default_wallet_id: null,
    })

    expect(user.defaultWalletId).toBeNull()
  })
})
