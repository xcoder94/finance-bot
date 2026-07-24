import { getAuthHeader } from './authHeader'

export type PerCurrencySummary = {
  currency: string
  income: number
  expense: number
  transfer_net: number
  net_change: number
  average_daily_expense: number
}

export type SummaryResponse = {
  by_currency: PerCurrencySummary[]
  day_of_week_expense: Record<string, number[]>
  day_of_week_income: Record<string, number[]>
}

export type CurrencyBalance = {
  currency: string
  balance: number
}

export type WalletBalancesResponse = {
  balances: CurrencyBalance[]
}

export type HistoryItem = {
  id: string
  type: string
  transaction_date: string
  amount: number
  currency: string
  wallet_id: string
  wallet_name: string
  wallet_translation_key: string | null
  to_wallet_id: string | null
  to_wallet_name: string | null
  to_wallet_translation_key: string | null
  to_amount: number | null
  to_currency: string | null
  income_category_name: string | null
  income_category_translation_key: string | null
  expense_category_name: string | null
  expense_category_translation_key: string | null
  expense_subcategory_name: string | null
  expense_subcategory_translation_key: string | null
  comment: string | null
  created_by: string | null
}

export type HistoryResponse = {
  items: HistoryItem[]
  total_count: number
}

export class HomeApiError extends Error {
  constructor(message?: string) {
    super(message ?? 'request failed')
  }
}

const HISTORY_FAR_PAST = '2020-01-01T00:00:00+00:00'

async function apiGet<T>(url: string): Promise<T> {
  let response: Response

  try {
    response = await fetch(url, {
      headers: {
        Authorization: getAuthHeader(),
      },
    })
  } catch {
    throw new HomeApiError()
  }

  if (!response.ok) {
    throw new HomeApiError()
  }

  return (await response.json()) as T
}

export function monthDateRange(year: number, month: number): { dateFrom: string; dateTo: string } {
  const dateFrom = new Date(Date.UTC(year, month - 1, 1)).toISOString()
  const lastDay = new Date(Date.UTC(year, month, 0)).getUTCDate()
  const dateTo = new Date(Date.UTC(year, month - 1, lastDay, 23, 59, 59, 999)).toISOString()
  return { dateFrom, dateTo }
}

export async function fetchSummary(year: number, month: number): Promise<SummaryResponse> {
  const { dateFrom, dateTo } = monthDateRange(year, month)
  const params = new URLSearchParams({
    date_from: dateFrom,
    date_to: dateTo,
  })
  return apiGet<SummaryResponse>(`/api/v1/analytics/summary?${params}`)
}

export async function fetchWalletBalances(): Promise<WalletBalancesResponse> {
  return apiGet<WalletBalancesResponse>('/api/v1/analytics/wallet-balances')
}

export async function fetchRecentHistory(): Promise<HistoryResponse> {
  const params = new URLSearchParams({
    date_from: HISTORY_FAR_PAST,
    date_to: new Date().toISOString(),
    limit: '3',
    offset: '0',
  })
  return apiGet<HistoryResponse>(`/api/v1/transactions/history?${params}`)
}
