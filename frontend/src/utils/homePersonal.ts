import type { PersonalSummaryResponse, PersonalWalletBalancesResponse } from '../api/home'
import type { Currency } from './formatCurrency'

export function shouldShowPersonalBlock(
  currenciesWithWallets: string[],
  selectedCurrency: Currency,
): boolean {
  return currenciesWithWallets.includes(selectedCurrency)
}

export function getPersonalSummaryForCurrency(
  summary: PersonalSummaryResponse,
  currency: Currency,
): { income: number; expense: number } {
  const entry = summary.by_currency.find((row) => row.currency === currency)
  return {
    income: entry?.income ?? 0,
    expense: entry?.expense ?? 0,
  }
}

export function getPersonalBalanceForCurrency(
  balances: PersonalWalletBalancesResponse,
  currency: Currency,
): number {
  return balances.balances.find((row) => row.currency === currency)?.balance ?? 0
}
