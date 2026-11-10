import { describe, expect, it } from 'vitest'

import { summaryCurrenciesPresent } from './historySummaryLine'

describe('summaryCurrenciesPresent', () => {
  const row = (currency: string, income: number, expense: number) => ({ currency, income, expense })
  it('UZS only when no USD operations', () => {
    expect(
      summaryCurrenciesPresent([row('UZS', 100, 50), row('USD', 0, 0)]).map((r) => r.currency),
    ).toEqual(['UZS'])
  })
  it('both when both present', () => {
    expect(
      summaryCurrenciesPresent([row('USD', 0, 5), row('UZS', 100, 0)]).map((r) => r.currency),
    ).toEqual(['UZS', 'USD'])
  })
  it('empty when nothing', () => {
    expect(summaryCurrenciesPresent([])).toEqual([])
  })
})
