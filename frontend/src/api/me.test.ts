import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./authHeader', () => ({
  getAuthHeader: () => 'Bearer test-token',
}))

import { mapMeResponse, patchMe } from './me'

describe('mapMeResponse', () => {
  it('maps budget_name to budgetName for the Home heading', () => {
    const user = mapMeResponse({
      id: 'user-1',
      telegram_id: 42,
      family_budget_id: 'family-1',
      role: 'owner',
      first_name: 'Alex',
      username: 'alex',
      language: 'ru',
      budget_name: 'Семейный бюджет',
      member_count: 3,
      default_wallet_id: null,
    })

    expect(user.budgetName).toBe('Семейный бюджет')
    expect(user.budgetName).not.toBe('Мои финансы')
  })

  it('maps default_wallet_id to defaultWalletId', () => {
    const user = mapMeResponse({
      id: 'user-1',
      telegram_id: 42,
      family_budget_id: 'family-1',
      role: 'owner',
      first_name: 'Alex',
      username: 'alex',
      language: 'ru',
      budget_name: 'Семейный бюджет',
      member_count: 1,
      default_wallet_id: 'wallet-abc',
    })

    expect(user.defaultWalletId).toBe('wallet-abc')
  })

  it('maps null default_wallet_id to null defaultWalletId', () => {
    const user = mapMeResponse({
      id: 'user-1',
      telegram_id: 42,
      family_budget_id: 'family-1',
      role: 'owner',
      first_name: null,
      username: null,
      language: 'ru',
      budget_name: 'Семейный бюджет',
      member_count: 1,
      default_wallet_id: null,
    })

    expect(user.defaultWalletId).toBeNull()
  })
})

describe('patchMe', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('PATCHes default_wallet_id and maps response', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'user-1',
        telegram_id: 42,
        family_budget_id: 'family-1',
        role: 'owner',
        first_name: 'Alex',
        username: 'alex',
        language: 'ru',
        budget_name: 'Семейный бюджет',
        member_count: 1,
        default_wallet_id: 'wallet-abc',
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const user = await patchMe({ default_wallet_id: 'wallet-abc' })

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/v1/me')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body as string)).toEqual({ default_wallet_id: 'wallet-abc' })
    expect(user.defaultWalletId).toBe('wallet-abc')
  })

  it('PATCHes language and maps response', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 'user-1',
        telegram_id: 42,
        family_budget_id: 'family-1',
        role: 'owner',
        first_name: null,
        username: null,
        language: 'uz',
        budget_name: 'Семейный бюджет',
        member_count: 1,
        default_wallet_id: null,
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const user = await patchMe({ language: 'uz' })

    expect(JSON.parse((fetchMock.mock.calls[0] as [string, RequestInit])[1].body as string)).toEqual({
      language: 'uz',
    })
    expect(user.language).toBe('uz')
  })
})
