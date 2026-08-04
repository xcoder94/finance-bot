import { getAuthHeader } from './authHeader'
import { HomeApiError } from './home'

export type GoalResponse = {
  id: string
  wallet_id: string
  name: string
  target_amount: number
  currency: string
  deadline: string | null
  status: string
  balance: number
  progress_pct: number | null
  excess_amount: number | null
  remaining_amount: number | null
  is_exactly_complete: boolean
  closed_at: string | null
  can_close: boolean
}

export type GoalCreatePayload = {
  wallet_id: string
  target_amount: number
  name?: string | null
  deadline?: string | null
}

export type GoalUpdatePayload = {
  name?: string | null
  target_amount?: number
  deadline?: string | null
}

export type GoalStatusFilter = 'active' | 'closed'

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

async function apiPost<T>(url: string, body?: unknown): Promise<T> {
  let response: Response

  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: getAuthHeader(),
        'Content-Type': 'application/json',
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new HomeApiError()
  }

  if (!response.ok) {
    throw new HomeApiError()
  }

  return (await response.json()) as T
}

export async function listGoals(status: GoalStatusFilter): Promise<GoalResponse[]> {
  return apiGet<GoalResponse[]>(`/api/v1/goals?status=${status}`)
}

export async function createGoal(payload: GoalCreatePayload): Promise<GoalResponse> {
  return apiPost<GoalResponse>('/api/v1/goals', payload)
}

export async function patchGoal(goalId: string, payload: GoalUpdatePayload): Promise<GoalResponse> {
  return apiPatch<GoalResponse>(`/api/v1/goals/${goalId}`, payload)
}

export async function closeGoal(goalId: string): Promise<GoalResponse> {
  return apiPost<GoalResponse>(`/api/v1/goals/${goalId}/close`)
}
