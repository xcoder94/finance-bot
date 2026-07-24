import type { AuthUser } from '../store/authStore'

type MeResponseJson = {
  id: string
  telegram_id: number
  family_budget_id: string
  role: string
  first_name: string | null
  username: string | null
  language: string
}

export type MeErrorType = 'unauthorized' | 'not_onboarded' | 'removed_from_family' | 'network'

export class MeRequestError extends Error {
  readonly errorType: MeErrorType

  constructor(errorType: MeErrorType, message?: string) {
    super(message ?? errorType)
    this.errorType = errorType
  }
}

function mapMeResponse(data: MeResponseJson): AuthUser {
  return {
    id: data.id,
    telegramId: data.telegram_id,
    familyBudgetId: data.family_budget_id,
    role: data.role,
    firstName: data.first_name,
    username: data.username,
    language: data.language,
  }
}

export async function fetchMe(initData: string): Promise<AuthUser> {
  let response: Response

  try {
    response = await fetch('/api/v1/me', {
      headers: {
        Authorization: `tma ${initData}`,
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
