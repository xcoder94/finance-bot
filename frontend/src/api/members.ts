import { getAuthHeader } from './authHeader'
import { HomeApiError } from './home'

export type MemberResponse = {
  id: string
  first_name: string | null
  username: string | null
  role: string
}

export type InviteLinkResponse = {
  invite_link: string
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

export async function getMembers(): Promise<MemberResponse[]> {
  return apiGet<MemberResponse[]>('/api/v1/members')
}

export async function getInviteLink(): Promise<InviteLinkResponse> {
  return apiGet<InviteLinkResponse>('/api/v1/members/invite-link')
}
