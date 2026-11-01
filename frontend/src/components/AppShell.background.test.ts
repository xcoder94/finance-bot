import { describe, expect, it } from 'vitest'

import { backgroundLocation } from './AppShell'

describe('backgroundLocation (forms open over Home, dev-fix7)', () => {
  it('returns the page the form was opened from', () => {
    const bg = { pathname: '/', search: '', hash: '', state: null, key: 'k' }
    expect(backgroundLocation({ background: bg })).toBe(bg)
  })

  it('is null for a direct entry or foreign state', () => {
    expect(backgroundLocation(null)).toBeNull()
    expect(backgroundLocation(undefined)).toBeNull()
    expect(backgroundLocation({ from: '/' })).toBeNull()
    expect(backgroundLocation({ background: 'x' })).toBeNull()
  })
})
