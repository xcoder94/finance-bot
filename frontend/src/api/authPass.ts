import { setAppPass } from './authHeader'

type PassResponse = {
  access_token: string
  token_type: string
  expires_in: number
}

export async function exchangeInitDataForPass(initData: string): Promise<string> {
  const response = await fetch('/api/v1/auth/pass', {
    method: 'POST',
    headers: { Authorization: `tma ${initData}` },
  })
  if (!response.ok) {
    throw new Error('pass_issue_failed')
  }
  const data = (await response.json()) as PassResponse
  setAppPass(data.access_token)
  return data.access_token
}
