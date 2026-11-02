import { describe, expect, it } from 'vitest'

import { schemeFromLaunchParams, detectSystemScheme, parsePreference, resolveTheme, schemeFromBgColor, type Theme, type ThemePreference } from './themeMode'

describe('resolveTheme: 3 modes x 2 Telegram themes', () => {
  const cases: Array<[ThemePreference, Theme, Theme]> = [
    ['system', 'dark', 'dark'],
    ['system', 'light', 'light'],
    ['light', 'dark', 'light'],
    ['light', 'light', 'light'],
    ['dark', 'dark', 'dark'],
    ['dark', 'light', 'dark'],
  ]
  it.each(cases)('%s + Telegram %s -> %s', (pref, tg, expected) => {
    expect(resolveTheme(pref, tg)).toBe(expected)
  })
  it('system with no information falls back to dark', () => {
    expect(resolveTheme('system', null)).toBe('dark')
  })
})

describe('detectSystemScheme', () => {
  it('Telegram wins over the browser', () => {
    expect(detectSystemScheme({ telegram: () => 'light', media: () => 'dark' })).toBe('light')
  })
  it('outside Telegram uses prefers-color-scheme', () => {
    expect(detectSystemScheme({ telegram: () => null, media: () => 'dark' })).toBe('dark')
    expect(detectSystemScheme({ telegram: () => null, media: () => 'light' })).toBe('light')
  })
  it('nothing known -> null', () => {
    expect(detectSystemScheme({ telegram: () => null, media: () => null })).toBeNull()
  })
})

describe('parsePreference / schemeFromBgColor', () => {
  it('accepts the three modes only', () => {
    expect(parsePreference('system')).toBe('system')
    expect(parsePreference('dark')).toBe('dark')
    expect(parsePreference('light')).toBe('light')
    expect(parsePreference('purple')).toBeNull()
    expect(parsePreference(null)).toBeNull()
  })
  it('classifies Telegram background colours', () => {
    expect(schemeFromBgColor('#17212b')).toBe('dark')
    expect(schemeFromBgColor('#ffffff')).toBe('light')
    expect(schemeFromBgColor('#000')).toBe('dark')
    expect(schemeFromBgColor('nope')).toBeNull()
    expect(schemeFromBgColor(undefined)).toBeNull()
  })
})

describe('schemeFromLaunchParams', () => {
  const q = (bg: string) => `tgWebAppVersion=8&tgWebAppThemeParams=${encodeURIComponent(JSON.stringify({ bg_color: bg }))}`
  it('reads the Telegram background from launch params', () => {
    expect(schemeFromLaunchParams('#' + q('#17212b'))).toBe('dark')
    expect(schemeFromLaunchParams(q('#ffffff'))).toBe('light')
  })
  it('garbage or empty -> null', () => {
    expect(schemeFromLaunchParams('')).toBeNull()
    expect(schemeFromLaunchParams('tgWebAppThemeParams=%7Bbad')).toBeNull()
    expect(schemeFromLaunchParams(null)).toBeNull()
  })
})
