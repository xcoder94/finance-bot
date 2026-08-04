import { describe, expect, it } from 'vitest'

import type { PersonalSummaryResponse, PersonalWalletBalancesResponse } from '../api/home'
import {
  getPersonalBalanceForCurrency,
  getPersonalSummaryForCurrency,
  shouldShowPersonalBlock,
} from './homePersonal'

describe('shouldShowPersonalBlock', () => {
  it('returns true when selected currency has a personal wallet', () => {
    expect(shouldShowPersonalBlock(['UZS'], 'UZS')).toBe(true)
    expect(shouldShowPersonalBlock(['UZS', 'USD'], 'USD')).toBe(true)
  })

  it('returns false when selected currency has no personal wallet', () => {
    expect(shouldShowPersonalBlock(['UZS'], 'USD')).toBe(false)
    expect(shouldShowPersonalBlock([], 'UZS')).toBe(false)
  })

  it('returns false for empty wallet currency list regardless of selection', () => {
    expect(shouldShowPersonalBlock([], 'UZS')).toBe(false)
    expect(shouldShowPersonalBlock([], 'USD')).toBe(false)
  })
})

describe('getPersonalSummaryForCurrency', () => {
  const summary: PersonalSummaryResponse = {
    currencies_with_wallets: ['UZS'],
    by_currency: [{ currency: 'UZS', income: 100, expense: 777 }],
  }

  it('returns month figures for the selected currency only', () => {
    expect(getPersonalSummaryForCurrency(summary, 'UZS')).toEqual({
      income: 100,
      expense: 777,
    })
  })

  it('returns zeroes when currency row is missing', () => {
    expect(getPersonalSummaryForCurrency(summary, 'USD')).toEqual({
      income: 0,
      expense: 0,
    })
  })
})

describe('getPersonalBalanceForCurrency', () => {
  const balances: PersonalWalletBalancesResponse = {
    currencies_with_wallets: ['UZS'],
    balances: [
      { currency: 'UZS', balance: -777 },
      { currency: 'USD', balance: 0 },
    ],
  }

  it('returns balance for the selected currency without conversion', () => {
    expect(getPersonalBalanceForCurrency(balances, 'UZS')).toBe(-777)
    expect(getPersonalBalanceForCurrency(balances, 'USD')).toBe(0)
  })

  it('returns zero when currency row is missing', () => {
    expect(getPersonalBalanceForCurrency(balances, 'EUR' as 'UZS')).toBe(0)
  })
})
