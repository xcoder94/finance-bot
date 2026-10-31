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
