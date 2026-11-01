import { getAuthHeader } from './authHeader'

export type AdminRetention = { returned: number; cohort: number; percent: number | null }
type Windows = { today: number; d7: number; d30: number }

export type AdminOverview = {
  totals: { users: number; families: number; families_multi: number }
  new_users: Windows
  new_families: Windows
  active: { dau: number; wau: number; mau: number }
  retention: { d7: AdminRetention; d30: AdminRetention }
  daily_active: { day: string; users: number }[]
  activity_since: string | null
}

export type AdminUser = {
  id: string
  first_name: string | null
  username: string | null
  phone: string | null
  language: 'ru' | 'uz'
  registered_at: string
  last_seen_at: string | null
  family_members: number
  family_role: 'owner' | 'member'
  operations_count: number
}

export type AdminUsersPage = { items: AdminUser[]; total: number; next_cursor: string | null }

export class AdminApiError extends Error {
  readonly status: number
  constructor(status: number) {
    super(`admin api ${status}`)
    this.status = status
  }
}

async function adminGet<T>(url: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, { headers: { Authorization: getAuthHeader() } })
  } catch {
    throw new AdminApiError(0)
  }
  if (!response.ok) {
    throw new AdminApiError(response.status)
  }
  return (await response.json()) as T
}

export function fetchAdminOverview(): Promise<AdminOverview> {
  return adminGet<AdminOverview>('/api/v1/admin/overview')
}

export function buildUsersUrl(params: { q?: string; cursor?: string | null; limit?: number }): string {
  const search = new URLSearchParams()
  const q = params.q?.trim()
  if (q) search.set('q', q)
  if (params.cursor) search.set('cursor', params.cursor)
  if (params.limit) search.set('limit', String(params.limit))
  const qs = search.toString()
  return `/api/v1/admin/users${qs ? `?${qs}` : ''}`
}

export function fetchAdminUsers(params: {
  q?: string
  cursor?: string | null
  limit?: number
}): Promise<AdminUsersPage> {
  return adminGet<AdminUsersPage>(buildUsersUrl(params))
}

export type AdminUsagePeriod = 'day' | 'week' | 'month'

export type AdminUsage = {
  period: AdminUsagePeriod
  operations: { text: number; voice: number; photo: number; app: number; unknown: number; total: number }
  ai: {
    calls: number
    error_calls: number
    calls_without_usage: number
    cost_incomplete: boolean
    input_tokens: number
    output_tokens: number
    cost_usd: number
    messages: number
    unparsed: number
    errors: number
    threshold_usd: number | null
    cost_today_usd: number
    /** Some of today's calls came without token counts (absent from older servers). */
    cost_today_incomplete?: boolean
  }
}

export function buildUsageUrl(period: AdminUsagePeriod): string {
  return `/api/v1/admin/usage?period=${period}`
}

export function fetchAdminUsage(period: AdminUsagePeriod): Promise<AdminUsage> {
  return adminGet<AdminUsage>(buildUsageUrl(period))
}
