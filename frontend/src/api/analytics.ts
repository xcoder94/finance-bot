import { getAuthHeader } from './authHeader'
import { fetchSummaryForRange } from './history'
import { HomeApiError, type SummaryResponse } from './home'

export type { SummaryResponse }
export { fetchSummaryForRange }

export type CategoryAmount = {
  category_id: string
  category_name: string
  category_translation_key: string | null
  color_index?: number
  amount: number
}

export type TrendEntry = {
  month: string
  currency: string
  income: number
  expense: number
}

export type SubcategoryAmount = {
  subcategory_id: string
  subcategory_name: string
  subcategory_translation_key: string | null
  color_index?: number
  amount: number
}

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

export async function fetchExpensesByCategory(
  currency: string,
  dateFrom: string,
  dateTo: string,
): Promise<CategoryAmount[]> {
  const params = new URLSearchParams({
    currency,
    date_from: dateFrom,
    date_to: dateTo,
  })
  return apiGet<CategoryAmount[]>(`/api/v1/analytics/expenses-by-category?${params}`)
}

export async function fetchIncomeByCategory(
  currency: string,
  dateFrom: string,
  dateTo: string,
): Promise<CategoryAmount[]> {
  const params = new URLSearchParams({
    currency,
    date_from: dateFrom,
    date_to: dateTo,
  })
  return apiGet<CategoryAmount[]>(`/api/v1/analytics/income-by-category?${params}`)
}

export async function fetchTrend(endMonth: string): Promise<TrendEntry[]> {
  const params = new URLSearchParams({ end_month: endMonth })
  return apiGet<TrendEntry[]>(`/api/v1/analytics/trend?${params}`)
}

export async function fetchExpensesBySubcategory(
  parentCategoryId: string,
  currency: string,
  dateFrom: string,
  dateTo: string,
): Promise<SubcategoryAmount[]> {
  const params = new URLSearchParams({
    parent_category_id: parentCategoryId,
    currency,
    date_from: dateFrom,
    date_to: dateTo,
  })
  return apiGet<SubcategoryAmount[]>(`/api/v1/analytics/expenses-by-subcategory?${params}`)
}
