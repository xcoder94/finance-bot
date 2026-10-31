import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./authHeader', () => ({ getAuthHeader: () => 'Bearer test-token' }))

import { fetchOnboarding, markDefaultWalletChecked } from './me'

const payload = {
  show: true,
  steps: { first_operation: true, default_wallet_checked: false, family_invited: false },
}

afterEach(() => vi.unstubAllGlobals())

describe('onboarding API', () => {
  it('GET /me/onboarding maps steps to camelCase', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => payload })
    vi.stubGlobal('fetch', fetchMock)
    const result = await fetchOnboarding()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/me/onboarding', {
      headers: { Authorization: 'Bearer test-token' },
    })
    expect(result).toEqual({
      show: true,
      steps: { firstOperation: true, defaultWalletChecked: false, familyInvited: false },
    })
  })

  it('POST default-wallet-checked uses POST without body', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => payload })
    vi.stubGlobal('fetch', fetchMock)
    await markDefaultWalletChecked()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/me/onboarding/default-wallet-checked', {
      method: 'POST',
      headers: { Authorization: 'Bearer test-token' },
    })
  })

  it('non-2xx rejects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }))
    await expect(fetchOnboarding()).rejects.toThrow()
  })
})
