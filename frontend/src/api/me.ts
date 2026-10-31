import type { AuthUser } from '../store/authStore'
import { getAuthHeader } from './authHeader'

type MeResponseJson = {
  id: string
  telegram_id: number
  family_budget_id: string
  role: string
  first_name: string | null
  username: string | null
  language: string
  budget_name: string
  member_count: number
  default_wallet_id: string | null
  evening_reminder_enabled?: boolean
  weekly_digest_enabled?: boolean
  receipt_photo_enabled?: boolean
  is_admin?: boolean
}

export type MeErrorType = 'unauthorized' | 'not_onboarded' | 'removed_from_family' | 'network'

export class MeRequestError extends Error {
  readonly errorType: MeErrorType

  constructor(errorType: MeErrorType, message?: string) {
    super(message ?? errorType)
    this.errorType = errorType
  }
}

export function mapMeResponse(data: MeResponseJson): AuthUser {
  return {
    id: data.id,
    telegramId: data.telegram_id,
    familyBudgetId: data.family_budget_id,
    role: data.role,
    firstName: data.first_name,
    username: data.username,
    language: data.language,
    budgetName: data.budget_name,
    memberCount: data.member_count,
    defaultWalletId: data.default_wallet_id,
    eveningReminderEnabled: data.evening_reminder_enabled ?? true,
    weeklyDigestEnabled: data.weekly_digest_enabled ?? true,
    receiptPhotoEnabled: data.receipt_photo_enabled ?? false,
    isAdmin: data.is_admin ?? false,
  }
}

export async function fetchMe(): Promise<AuthUser> {
  let response: Response

  try {
    response = await fetch('/api/v1/me', {
      headers: {
        Authorization: getAuthHeader(),
      },
    })
  } catch {
    throw new MeRequestError('network')
  }

  if (response.status === 401) {
    throw new MeRequestError('unauthorized')
  }

  if (response.status === 404) {
    throw new MeRequestError('not_onboarded')
  }

  if (response.status === 403) {
    throw new MeRequestError('removed_from_family')
  }

  if (!response.ok) {
    throw new MeRequestError('network')
  }

  const data = (await response.json()) as MeResponseJson
  return mapMeResponse(data)
}

export type MeUpdatePayload = {
  default_wallet_id?: string | null
  language?: 'ru' | 'uz'
  evening_reminder_enabled?: boolean
  weekly_digest_enabled?: boolean
}

export async function patchMe(payload: MeUpdatePayload): Promise<AuthUser> {
  let response: Response

  try {
    response = await fetch('/api/v1/me', {
      method: 'PATCH',
      headers: {
        Authorization: getAuthHeader(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })
  } catch {
    throw new MeRequestError('network')
  }

  if (response.status === 401) {
    throw new MeRequestError('unauthorized')
  }

  if (response.status === 404) {
    throw new MeRequestError('not_onboarded')
  }

  if (response.status === 403) {
    throw new MeRequestError('removed_from_family')
  }

  if (!response.ok) {
    throw new MeRequestError('network')
  }

  const data = (await response.json()) as MeResponseJson
  return mapMeResponse(data)
}

export type OnboardingState = {
  show: boolean
  steps: { firstOperation: boolean; defaultWalletChecked: boolean; familyInvited: boolean }
}

type OnboardingJson = {
  show: boolean
  steps: { first_operation: boolean; default_wallet_checked: boolean; family_invited: boolean }
}

function mapOnboarding(data: OnboardingJson): OnboardingState {
  return {
    show: data.show,
    steps: {
      firstOperation: data.steps.first_operation,
      defaultWalletChecked: data.steps.default_wallet_checked,
      familyInvited: data.steps.family_invited,
    },
  }
}

async function onboardingRequest(url: string, method: 'GET' | 'POST'): Promise<OnboardingState> {
  let response: Response
  try {
    response = await fetch(
      url,
      method === 'GET'
        ? { headers: { Authorization: getAuthHeader() } }
        : { method, headers: { Authorization: getAuthHeader() } },
    )
  } catch {
    throw new MeRequestError('network')
  }
  if (!response.ok) {
    throw new MeRequestError('network')
  }
  return mapOnboarding((await response.json()) as OnboardingJson)
}

export function fetchOnboarding(): Promise<OnboardingState> {
  return onboardingRequest('/api/v1/me/onboarding', 'GET')
}

export function markDefaultWalletChecked(): Promise<OnboardingState> {
  return onboardingRequest('/api/v1/me/onboarding/default-wallet-checked', 'POST')
}
