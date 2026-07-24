import { getAuthHeader } from './authHeader'

export type Wallet = {
  id: string
  name: string
  currency: string
  translation_key: string | null
  transaction_count: number
}

export type IncomeCategory = {
  id: string
  name: string
  translation_key: string | null
  transaction_count: number
}

export type ExpenseCategory = {
  id: string
  name: string
  translation_key: string | null
  parent_id: string | null
  transaction_count: number
}

export type IncomeCreatePayload = {
  transaction_date: string
  amount: number
  wallet_id: string
  income_category_id: string
  comment?: string | null
}

export type ExpenseCreatePayload = {
  transaction_date: string
  amount: number
  wallet_id: string
  expense_category_id: string
  comment?: string | null
}

export type TransferCreatePayload = {
  transaction_date: string
  wallet_id: string
  to_wallet_id: string
  amount: number
  rate?: number
  comment?: string | null
}

export type ExpenseCategoryCreatePayload = {
  name: string
  parent_id: string
}

export type IncomeUpdatePayload = IncomeCreatePayload
export type ExpenseUpdatePayload = ExpenseCreatePayload
export type TransferUpdatePayload = TransferCreatePayload

export type TransactionResponse = {
  id: string
  type: string
  transaction_date: string
  amount: number
  wallet_id: string
  to_wallet_id: string | null
  to_amount: number | null
  rate: number | null
  income_category_id: string | null
  expense_category_id: string | null
  comment: string | null
  created_by_user_id: string
}

export class TransactionsApiError extends Error {
  constructor(message?: string) {
    super(message ?? 'request failed')
  }
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
    throw new TransactionsApiError()
  }

  if (!response.ok) {
    throw new TransactionsApiError()
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
    throw new TransactionsApiError()
  }

  if (!response.ok) {
    throw new TransactionsApiError()
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
    throw new TransactionsApiError()
  }

  if (!response.ok) {
    throw new TransactionsApiError()
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
    throw new TransactionsApiError()
  }

  if (!response.ok) {
    throw new TransactionsApiError()
  }

  return (await response.json()) as T
}

export async function fetchWallets(): Promise<Wallet[]> {
  return apiGet<Wallet[]>('/api/v1/wallets')
}

export async function fetchIncomeCategories(): Promise<IncomeCategory[]> {
  return apiGet<IncomeCategory[]>('/api/v1/categories/income')
}

export async function fetchExpenseCategories(): Promise<ExpenseCategory[]> {
  return apiGet<ExpenseCategory[]>('/api/v1/categories/expense')
}

export async function createExpenseCategory(
  payload: ExpenseCategoryCreatePayload,
): Promise<ExpenseCategory> {
  return apiPost<ExpenseCategory>('/api/v1/categories/expense', payload)
}

export async function createIncomeTransaction(
  payload: IncomeCreatePayload,
): Promise<TransactionResponse> {
  return apiPost<TransactionResponse>('/api/v1/transactions/income', payload)
}

export async function createExpenseTransaction(
  payload: ExpenseCreatePayload,
): Promise<TransactionResponse> {
  return apiPost<TransactionResponse>('/api/v1/transactions/expense', payload)
}

export async function createTransferTransaction(
  payload: TransferCreatePayload,
): Promise<TransactionResponse> {
  return apiPost<TransactionResponse>('/api/v1/transactions/transfer', payload)
}

export async function fetchTransaction(transactionId: string): Promise<TransactionResponse> {
  return apiGet<TransactionResponse>(`/api/v1/transactions/${transactionId}`)
}

export async function updateIncomeTransaction(
  transactionId: string,
  payload: IncomeUpdatePayload,
): Promise<TransactionResponse> {
  return apiPatch<TransactionResponse>(`/api/v1/transactions/${transactionId}`, payload)
}

export async function updateExpenseTransaction(
  transactionId: string,
  payload: ExpenseUpdatePayload,
): Promise<TransactionResponse> {
  return apiPatch<TransactionResponse>(`/api/v1/transactions/${transactionId}`, payload)
}

export async function updateTransferTransaction(
  transactionId: string,
  payload: TransferUpdatePayload,
): Promise<TransactionResponse> {
  return apiPatch<TransactionResponse>(`/api/v1/transactions/${transactionId}`, payload)
}

export async function deleteTransaction(transactionId: string): Promise<TransactionResponse> {
  return apiDelete<TransactionResponse>(`/api/v1/transactions/${transactionId}`)
}
