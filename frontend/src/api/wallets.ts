import { getAuthHeader } from './authHeader'
import { HomeApiError } from './home'

export type WalletResponse = {
  id: string
  name: string
  currency: string
  translation_key: string | null
  transaction_count: number
}

export type WalletDeleteResponse = {
  id: string
  name: string
  currency: string
  affected_transactions_count: number
}

export type WalletCreatePayload = {
  name: string
  currency: 'UZS' | 'USD'
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

export async function getWallets(): Promise<WalletResponse[]> {
  return apiGet<WalletResponse[]>('/api/v1/wallets')
}

export async function createWallet(payload: WalletCreatePayload): Promise<WalletResponse> {
  return apiPost<WalletResponse>('/api/v1/wallets', payload)
}

export async function deleteWallet(walletId: string): Promise<WalletDeleteResponse> {
  return apiDelete<WalletDeleteResponse>(`/api/v1/wallets/${walletId}`)
}
