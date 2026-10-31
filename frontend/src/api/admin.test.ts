import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./authHeader', () => ({ getAuthHeader: () => 'Bearer test-token' }))

import { AdminApiError, buildUsersUrl, fetchAdminOverview, fetchAdminUsers } from './admin'

afterEach(() => vi.unstubAllGlobals())

describe('buildUsersUrl', () => {
  it('has no query string by default', () => {
    expect(buildUsersUrl({})).toBe('/api/v1/admin/users')
  })
  it('encodes q (trimmed) and cursor, omits empty ones', () => {
    expect(buildUsersUrl({ q: '  @ali v ', cursor: 'a+b=', limit: 50 })).toBe(
      '/api/v1/admin/users?q=%40ali+v&cursor=a%2Bb%3D&limit=50',
    )
    expect(buildUsersUrl({ q: '   ', cursor: null })).toBe('/api/v1/admin/users')
  })
})

describe('admin requests', () => {
  it('sends the bearer header and returns JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [], total: 0, next_cursor: null }) })
    vi.stubGlobal('fetch', fetchMock)
    await expect(fetchAdminUsers({ q: 'x' })).resolves.toEqual({ items: [], total: 0, next_cursor: null })
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/admin/users?q=x', {
      headers: { Authorization: 'Bearer test-token' },
    })
  })
  it('throws AdminApiError with the status on non-2xx (404 = not admin)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }))
    await expect(fetchAdminOverview()).rejects.toMatchObject({ status: 404 })
    await expect(fetchAdminOverview()).rejects.toBeInstanceOf(AdminApiError)
  })
  it('maps a network failure to status 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('down')))
    await expect(fetchAdminOverview()).rejects.toMatchObject({ status: 0 })
  })
})
