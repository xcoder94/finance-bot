import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./authHeader', () => ({
  getAuthHeader: () => 'Bearer test-token',
}))

import { fetchExpenseComparison, fetchIncomeByCategory, fetchTrend } from './analytics'

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

describe('fetchExpenseComparison', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests the comparison endpoint with currency and dates', async () => {
    const body = {
      currency: 'UZS',
      total: 1120000,
      prev_total: 1000000,
      prev_date_from: '2026-10-01T00:00:00+05:00',
      prev_date_to: '2026-10-31T23:59:59.999999+05:00',
    }
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => body })
    vi.stubGlobal('fetch', fetchMock)

    const result = await fetchExpenseComparison('UZS', '2026-11-01T00:00:00+05:00', '2026-11-30T23:59:59+05:00')

    const [url] = fetchMock.mock.calls[0] as [string]
    const parsed = new URL(url, 'http://localhost')
    expect(parsed.pathname).toBe('/api/v1/analytics/expense-comparison')
    expect(parsed.searchParams.get('currency')).toBe('UZS')
    expect(parsed.searchParams.get('date_from')).toBe('2026-11-01T00:00:00+05:00')
    expect(result).toEqual(body)
  })

  it('income-by-category passes the range', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] })
    vi.stubGlobal('fetch', fetchMock)
    await fetchIncomeByCategory('UZS', 'a', 'b')
    const [url] = fetchMock.mock.calls[0] as [string]
    expect(url).toContain('/api/v1/analytics/income-by-category?')
  })
})
