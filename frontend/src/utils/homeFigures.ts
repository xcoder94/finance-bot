import type { SummaryResponse, WalletBalancesResponse } from '../api/home'
import type { AuthUser } from '../store/authStore'
import type { Currency } from './formatCurrency'

export function getSummaryForCurrency(
  summary: SummaryResponse,
  currency: Currency,
): { income: number; expense: number } {
  const entry = summary.by_currency.find((row) => row.currency === currency)
  return {
    income: entry?.income ?? 0,
    expense: entry?.expense ?? 0,
  }
}

export function getBalanceForCurrency(
  balances: WalletBalancesResponse,
  currency: Currency,
): number {
  return balances.balances.find((row) => row.currency === currency)?.balance ?? 0
}

export function getHomeBudgetHeading(user: Pick<AuthUser, 'budgetName'> | null): string {
  return user?.budgetName ?? ''
}
