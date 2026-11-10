import { describe, expect, it } from 'vitest'

import { sharedUzsWalletsTotal } from './homeWallets'

const w = (currency: string, balance: number, is_personal = false) =>
  ({ id: 'x', name: 'w', currency, translation_key: null, transaction_count: 0, is_personal, has_active_goal: false, balance })

describe('sharedUzsWalletsTotal', () => {
  it('sums only shared UZS wallets', () => {
    expect(
      sharedUzsWalletsTotal([w('UZS', 10_000_000), w('UZS', 2_400_000), w('USD', 500), w('UZS', 777, true)]),
    ).toBe(12_400_000)
  })
  it('is 0 without wallets', () => {
    expect(sharedUzsWalletsTotal([])).toBe(0)
  })
})
