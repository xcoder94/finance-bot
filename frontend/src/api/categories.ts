import { getAuthHeader } from './authHeader'
import { HomeApiError } from './home'

export type IncomeCategoryResponse = {
  id: string
  name: string
  translation_key: string | null
  transaction_count: number
}

export type IncomeCategoryDeleteResponse = {
  id: string
  name: string
  affected_transactions_count: number
}

export type IncomeCategoryCreatePayload = {
  name: string
}

export type IncomeCategoryUpdatePayload = {
  name: string
}

export type ExpenseCategoryResponse = {
  id: string
  name: string
  translation_key: string | null
  parent_id: string | null
  transaction_count: number
}

export type ExpenseCategoryDeleteResponse = {
  id: string
  name: string
  parent_id: string | null
  affected_transactions_count: number
}

export type ExpenseCategoryCreatePayload = {
  name: string
  parent_id?: string | null
}

export type ExpenseCategoryUpdatePayload = {
  name: string
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

async function apiPost<T>(url: string, body: unknown): Promise<T> {
  let response: Response

  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: getAuthHeader(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
  } catch {
    throw new HomeApiError()
  }

  if (!response.ok) {
    throw new HomeApiError()
  }

  return (await response.json()) as T
}

async function apiDelete<T>(url: string): Promise<T> {
  let response: Response

  try {
    response = await fetch(url, {
      method: 'DELETE',
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

async function apiPatch<T>(url: string, body: unknown): Promise<T> {
  let response: Response

  try {
    response = await fetch(url, {
      method: 'PATCH',
      headers: {
        Authorization: getAuthHeader(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
  } catch {
    throw new HomeApiError()
  }

  if (!response.ok) {
    throw new HomeApiError()
  }

  return (await response.json()) as T
}

export async function getIncomeCategories(): Promise<IncomeCategoryResponse[]> {
  return apiGet<IncomeCategoryResponse[]>('/api/v1/categories/income')
}

export async function createIncomeCategory(
  payload: IncomeCategoryCreatePayload,
): Promise<IncomeCategoryResponse> {
  return apiPost<IncomeCategoryResponse>('/api/v1/categories/income', payload)
}

export async function patchIncomeCategory(
  categoryId: string,
  payload: IncomeCategoryUpdatePayload,
): Promise<IncomeCategoryResponse> {
  return apiPatch<IncomeCategoryResponse>(`/api/v1/categories/income/${categoryId}`, payload)
}

export async function deleteIncomeCategory(
  categoryId: string,
): Promise<IncomeCategoryDeleteResponse> {
  return apiDelete<IncomeCategoryDeleteResponse>(`/api/v1/categories/income/${categoryId}`)
}

export async function getExpenseCategories(): Promise<ExpenseCategoryResponse[]> {
  return apiGet<ExpenseCategoryResponse[]>('/api/v1/categories/expense')
}

export async function createExpenseCategory(
  payload: ExpenseCategoryCreatePayload,
): Promise<ExpenseCategoryResponse> {
  return apiPost<ExpenseCategoryResponse>('/api/v1/categories/expense', payload)
}

export async function patchExpenseCategory(
  categoryId: string,
  payload: ExpenseCategoryUpdatePayload,
): Promise<ExpenseCategoryResponse> {
  return apiPatch<ExpenseCategoryResponse>(`/api/v1/categories/expense/${categoryId}`, payload)
}

export async function deleteExpenseCategory(
  categoryId: string,
): Promise<ExpenseCategoryDeleteResponse> {
  return apiDelete<ExpenseCategoryDeleteResponse>(`/api/v1/categories/expense/${categoryId}`)
}
