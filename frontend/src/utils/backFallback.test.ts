import { describe, expect, it } from 'vitest'

import { backFallbackPath } from './backFallback'

describe('backFallbackPath', () => {
  it('sends /admin opened directly (no history) to /settings', () => {
    expect(backFallbackPath('/admin', null)).toBe('/settings')
  })
  it('sends edit pages to history by default', () => {
    expect(backFallbackPath('/edit-transaction', null)).toBe('/history')
  })
  it('sends other pages to home', () => {
    expect(backFallbackPath('/settings', null)).toBe('/')
  })
})

describe('backFallbackPath /wallets', () => {
  it('goes home', () => {
    expect(backFallbackPath('/wallets', null)).toBe('/')
  })
})

describe('backFallbackPath /wallets/:id', () => {
  it('goes to the wallets list', () => {
    expect(backFallbackPath('/wallets/x', null)).toBe('/wallets')
    expect(backFallbackPath('/wallets/x/', null)).toBe('/wallets')
  })
})
