import { describe, expect, it } from 'vitest'

import type { SummaryResponse, WalletBalancesResponse } from '../api/home'
import {
  getBalanceForCurrency,
  getHomeBudgetHeading,
  getSummaryForCurrency,
} from './homeFigures'

const dualCurrencySummary: SummaryResponse = {
  by_currency: [
    {
      currency: 'UZS',
      income: 500000,
      expense: 100000,
      transfer_net: 0,
      net_change: 400000,
      average_daily_expense: 3225.8,
      most_expensive_weekday: 0,
      most_expensive_weekday_average: 5000,
    },
    {
      currency: 'USD',
      income: 200,
      expense: 10,
      transfer_net: 0,
      net_change: 190,
      average_daily_expense: 0.32,
      most_expensive_weekday: null,
      most_expensive_weekday_average: 0,
    },
  ],
  day_of_week_expense: {},
  day_of_week_income: {},
}

const dualCurrencyBalances: WalletBalancesResponse = {
  balances: [
    { currency: 'UZS', balance: 1_500_000 },
    { currency: 'USD', balance: 350 },
  ],
}

describe('getSummaryForCurrency', () => {
  it('returns UZS figures without mixing USD amounts', () => {
    const uzs = getSummaryForCurrency(dualCurrencySummary, 'UZS')
    expect(uzs).toEqual({ income: 500000, expense: 100000 })
    expect(uzs.expense).not.toBe(100010)
    expect(uzs.income).not.toBe(500200)
  })

  it('returns USD figures without mixing UZS amounts', () => {
    const usd = getSummaryForCurrency(dualCurrencySummary, 'USD')
    expect(usd).toEqual({ income: 200, expense: 10 })
    expect(usd.expense).not.toBe(100010)
    expect(usd.income).not.toBe(500200)
  })

  it('returns zeroes when currency row is missing', () => {
    expect(getSummaryForCurrency(dualCurrencySummary, 'EUR' as 'UZS')).toEqual({
      income: 0,
      expense: 0,
    })
  })
})

describe('getBalanceForCurrency', () => {
  it('returns UZS balance without converting USD', () => {
    expect(getBalanceForCurrency(dualCurrencyBalances, 'UZS')).toBe(1_500_000)
    expect(getBalanceForCurrency(dualCurrencyBalances, 'UZS')).not.toBe(1_500_350)
  })

  it('returns USD balance without converting UZS', () => {
    expect(getBalanceForCurrency(dualCurrencyBalances, 'USD')).toBe(350)
    expect(getBalanceForCurrency(dualCurrencyBalances, 'USD')).not.toBe(1_500_350)
  })

  it('returns zero when currency row is missing', () => {
    expect(getBalanceForCurrency(dualCurrencyBalances, 'EUR' as 'UZS')).toBe(0)
  })
})

describe('getHomeBudgetHeading', () => {
  it('uses budgetName from user profile', () => {
    expect(getHomeBudgetHeading({ budgetName: 'Семейный бюджет' })).toBe('Семейный бюджет')
  })

  it('returns empty string when user is absent', () => {
    expect(getHomeBudgetHeading(null)).toBe('')
  })

  it('does not fall back to the legacy default title', () => {
    const heading = getHomeBudgetHeading({ budgetName: 'Семейный бюджет' })
    expect(heading).not.toBe('Мои финансы')
  })
})
