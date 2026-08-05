import { getAuthHeader } from './authHeader'
import { HomeApiError } from './home'

export type DemoDataStatusResponse = {
  has_demo_data: boolean
}

export type DemoDataClearResponse = {
  cleared_count: number
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

export async function getDemoDataStatus(): Promise<DemoDataStatusResponse> {
  return apiGet<DemoDataStatusResponse>('/api/v1/demo-data/status')
}

export async function clearDemoData(): Promise<DemoDataClearResponse> {
  return apiDelete<DemoDataClearResponse>('/api/v1/demo-data')
}
