import { getAuthHeader } from './authHeader'
import { HomeApiError } from './home'

export type MemberResponse = {
  id: string
  first_name: string | null
  username: string | null
  role: string
  created_at: string
}

export type InviteLinkResponse = {
  invite_link: string
}

export type MemberDeleteResponse = {
  id: string
  first_name: string | null
  role: string
}

export type TransferResponse = {
  id: string
  to_user_id: string
  status: string
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

async function apiPost<T>(url: string): Promise<T> {
  let response: Response

  try {
    response = await fetch(url, {
      method: 'POST',
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

export async function getMembers(): Promise<MemberResponse[]> {
  return apiGet<MemberResponse[]>('/api/v1/members')
}

export async function getInviteLink(): Promise<InviteLinkResponse> {
  return apiGet<InviteLinkResponse>('/api/v1/members/invite-link')
}

export async function regenerateInviteLink(): Promise<InviteLinkResponse> {
  return apiPost<InviteLinkResponse>('/api/v1/members/invite-link/regenerate')
}

export async function removeMember(memberId: string): Promise<MemberDeleteResponse> {
  return apiDelete<MemberDeleteResponse>(`/api/v1/members/${memberId}`)
}

export async function leaveFamily(): Promise<MemberDeleteResponse> {
  return apiPost<MemberDeleteResponse>('/api/v1/members/leave')
}

export async function requestTransfer(memberId: string): Promise<TransferResponse> {
  return apiPost<TransferResponse>(`/api/v1/members/${memberId}/transfer`)
}
