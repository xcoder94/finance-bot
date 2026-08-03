import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./authHeader', () => ({
  getAuthHeader: () => 'Bearer test-token',
}))

import { fetchTrend } from './analytics'

describe('fetchTrend', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests trend with end_month query param', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchTrend('2026-08')

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const parsed = new URL(url, 'http://localhost')
    expect(parsed.pathname).toBe('/api/v1/analytics/trend')
    expect(parsed.searchParams.get('end_month')).toBe('2026-08')
    expect(init.headers).toMatchObject({
      Authorization: expect.any(String),
    })
  })
})
