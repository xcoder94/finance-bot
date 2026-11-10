import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./authHeader', () => ({
  getAuthHeader: () => 'Bearer test-token',
}))

import { fetchHistoryPage } from './history'

describe('fetchHistoryPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requests history without expense_category_id by default', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total_count: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchHistoryPage(
      '2026-08-01T00:00:00.000+05:00',
      '2026-08-31T23:59:59.999+05:00',
      20,
      0,
    )

    const [url] = fetchMock.mock.calls[0] as [string]
    const parsed = new URL(url, 'http://localhost')
    expect(parsed.searchParams.get('expense_category_id')).toBeNull()
  })

  it('passes expense_category_id when provided', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total_count: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchHistoryPage(
      '2026-08-01T00:00:00.000+05:00',
      '2026-08-31T23:59:59.999+05:00',
      20,
      0,
      'sub-groceries',
    )

    const [url] = fetchMock.mock.calls[0] as [string]
    const parsed = new URL(url, 'http://localhost')
    expect(parsed.searchParams.get('expense_category_id')).toBe('sub-groceries')
  })
})

describe('fetchHistoryPage wallet_id', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const run = async (walletId?: string) => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total_count: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)
    await fetchHistoryPage('2026-11-01T00:00:00.000+05:00', '2026-11-30T23:59:59.999+05:00', 50, 0, undefined, walletId)
    const [url] = fetchMock.mock.calls[0] as [string]
    return new URL(url, 'http://localhost').searchParams
  }

  it('sends wallet_id when given', async () => {
    const params = await run('w-1')
    expect(params.get('wallet_id')).toBe('w-1')
    expect(params.get('date_from')).toBe('2026-11-01T00:00:00.000+05:00')
    expect(params.get('limit')).toBe('50')
  })

  it('omits wallet_id by default', async () => {
    expect((await run()).has('wallet_id')).toBe(false)
  })
})

describe('fetchHistoryPage uncategorized', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  async function call(expenseCategoryId?: string, uncategorized?: boolean) {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total_count: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)
    await fetchHistoryPage('2026-08-01T00:00:00.000+05:00', '2026-08-31T23:59:59.999+05:00', 20, 0, expenseCategoryId, undefined, uncategorized)
    const [url] = fetchMock.mock.calls[0] as [string]
    return new URL(url, 'http://localhost').searchParams
  }

  it('sends uncategorized=true without expense_category_id', async () => {
    const params = await call(undefined, true)
    expect(params.get('uncategorized')).toBe('true')
    expect(params.get('expense_category_id')).toBeNull()
  })

  it('never sends both (API would answer 422)', async () => {
    const params = await call('cat-1', true)
    expect(params.get('uncategorized')).toBeNull()
    expect(params.get('expense_category_id')).toBe('cat-1')
  })

  it('omits uncategorized by default', async () => {
    expect((await call()).get('uncategorized')).toBeNull()
  })

  it('passes the selected currency when provided (B17)', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total_count: 0 }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await fetchHistoryPage('2026-08-01T00:00:00.000+05:00', '2026-08-31T23:59:59.999+05:00', 20, 0, 'c1', undefined, false, 'USD')

    const [url] = fetchMock.mock.calls[0] as [string]
    expect(new URL(url, 'http://localhost').searchParams.get('currency')).toBe('USD')
  })
})
