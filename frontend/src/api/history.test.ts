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
