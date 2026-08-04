import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./authHeader', () => ({
  getAuthHeader: () => 'Bearer test-token',
}))

import {
  fetchPersonalSummary,
  fetchPersonalWalletBalances,
  fetchRecentHistory,
  monthDateRange,
} from './home'

describe('monthDateRange', () => {
  it('uses Asia/Tashkent day boundaries for the calendar month', () => {
    expect(monthDateRange(2026, 8)).toEqual({
      dateFrom: '2026-08-01T00:00:00.000+05:00',
      dateTo: '2026-08-31T23:59:59.999+05:00',
    })
  })

  it('handles February in a leap year', () => {
    expect(monthDateRange(2024, 2)).toEqual({
      dateFrom: '2024-02-01T00:00:00.000+05:00',
      dateTo: '2024-02-29T23:59:59.999+05:00',
    })
  })
})

describe('fetchRecentHistory', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests month-scoped history with limit 3', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total_count: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchRecentHistory(2026, 8)

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const parsed = new URL(url, 'http://localhost')
    expect(parsed.pathname).toBe('/api/v1/transactions/history')
    expect(parsed.searchParams.get('date_from')).toBe('2026-08-01T00:00:00.000+05:00')
    expect(parsed.searchParams.get('date_to')).toBe('2026-08-31T23:59:59.999+05:00')
    expect(parsed.searchParams.get('limit')).toBe('3')
    expect(parsed.searchParams.get('offset')).toBe('0')
    expect(init.headers).toMatchObject({
      Authorization: expect.any(String),
    })
  })
})

describe('fetchPersonalSummary', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests month-scoped personal summary', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        currencies_with_wallets: ['UZS'],
        by_currency: [{ currency: 'UZS', income: 0, expense: 777 }],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchPersonalSummary(2026, 8)

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const parsed = new URL(url, 'http://localhost')
    expect(parsed.pathname).toBe('/api/v1/analytics/personal-summary')
    expect(parsed.searchParams.get('date_from')).toBe('2026-08-01T00:00:00.000+05:00')
    expect(parsed.searchParams.get('date_to')).toBe('2026-08-31T23:59:59.999+05:00')
    expect(init.headers).toMatchObject({
      Authorization: expect.any(String),
    })
  })
})

describe('fetchPersonalWalletBalances', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests personal wallet balances', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        currencies_with_wallets: ['UZS'],
        balances: [{ currency: 'UZS', balance: -777 }],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchPersonalWalletBalances()

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    const parsed = new URL(url, 'http://localhost')
    expect(parsed.pathname).toBe('/api/v1/analytics/personal-wallet-balances')
    expect(init.headers).toMatchObject({
      Authorization: expect.any(String),
    })
  })
})
