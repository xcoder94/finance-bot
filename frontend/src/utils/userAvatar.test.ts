import { describe, expect, it } from 'vitest'

import { parseInitDataUser, settingsBackTarget, userInitials } from './userAvatar'

const raw = (user: object) => `query_id=x&user=${encodeURIComponent(JSON.stringify(user))}`

describe('userAvatar utils', () => {
  it('reads photo_url and names from initData', () => {
    expect(
      parseInitDataUser(raw({ first_name: 'Ali', last_name: 'Karimov', photo_url: 'https://t.me/a.jpg' })),
    ).toEqual({ firstName: 'Ali', lastName: 'Karimov', photoUrl: 'https://t.me/a.jpg' })
  })
  it('returns nulls for missing/broken initData', () => {
    expect(parseInitDataUser(undefined).photoUrl).toBeNull()
    expect(parseInitDataUser('user=%7Bbroken').photoUrl).toBeNull()
    expect(parseInitDataUser(raw({ first_name: 'Ali' })).photoUrl).toBeNull()
  })
  it('builds initials: first+last, else first letter', () => {
    expect(userInitials('ali', 'karimov')).toBe('AK')
    expect(userInitials('Мария', null)).toBe('М')
    expect(userInitials(null, null)).toBe('?')
  })
  it('settings back target defaults to Home', () => {
    expect(settingsBackTarget(null)).toBe('/')
    expect(settingsBackTarget({ from: '/' })).toBe('/')
    expect(settingsBackTarget({ from: '/goals' })).toBe('/goals')
    expect(settingsBackTarget({ from: 'http://evil' })).toBe('/')
  })
  it('rejects protocol-relative and backslash redirect targets', () => {
    expect(settingsBackTarget({ from: '//evil.example' })).toBe('/')
    expect(settingsBackTarget({ from: '/\\evil.example' })).toBe('/')
  })
  it('accepts only https photo_url', () => {
    expect(parseInitDataUser(raw({ first_name: 'A', photo_url: 'http://t.me/a.jpg' })).photoUrl).toBeNull()
    expect(parseInitDataUser(raw({ first_name: 'A', photo_url: 'javascript:alert(1)' })).photoUrl).toBeNull()
    expect(parseInitDataUser(raw({ first_name: 'A', photo_url: 'data:image/png;base64,AA' })).photoUrl).toBeNull()
    expect(parseInitDataUser(raw({ first_name: 'A', photo_url: 'nonsense' })).photoUrl).toBeNull()
  })
})
