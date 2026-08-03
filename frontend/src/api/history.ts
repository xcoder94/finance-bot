import { getAuthHeader } from './authHeader'
import {
  HomeApiError,
  type HistoryItem,
  type HistoryResponse,
  type SummaryResponse,
} from './home'

export type { HistoryItem, HistoryResponse, SummaryResponse }

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

export async function fetchSummaryForRange(
  dateFrom: string,
  dateTo: string,
): Promise<SummaryResponse> {
  const params = new URLSearchParams({
    date_from: dateFrom,
    date_to: dateTo,
  })
  return apiGet<SummaryResponse>(`/api/v1/analytics/summary?${params}`)
}

export async function fetchHistoryPage(
  dateFrom: string,
  dateTo: string,
  limit: number,
  offset: number,
  expenseCategoryId?: string,
): Promise<HistoryResponse> {
  const params = new URLSearchParams({
    date_from: dateFrom,
    date_to: dateTo,
    limit: String(limit),
    offset: String(offset),
  })
  if (expenseCategoryId) {
    params.set('expense_category_id', expenseCategoryId)
  }
  return apiGet<HistoryResponse>(`/api/v1/transactions/history?${params}`)
}
