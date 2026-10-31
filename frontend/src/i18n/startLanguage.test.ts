import { describe, expect, it } from 'vitest'

import {
  LAST_LANGUAGE_KEY,
  pickStartLanguage,
  readTelegramLanguageCode,
  rememberLanguage,
} from './startLanguage'

function memoryStorage(initial: Record<string, string> = {}) {
  const data = { ...initial }
  return {
    getItem: (k: string) => data[k] ?? null,
    setItem: (k: string, v: string) => {
      data[k] = v
    },
    data,
  }
}

describe('pickStartLanguage', () => {
  it('prefers the last known language', () => {
    expect(pickStartLanguage('uz', 'ru')).toBe('uz')
    expect(pickStartLanguage('ru', 'uz')).toBe('ru')
  })

  it('falls back to Telegram language_code: uz -> uz, anything else -> ru', () => {
    expect(pickStartLanguage(null, 'uz')).toBe('uz')
    expect(pickStartLanguage(null, 'uz-UZ')).toBe('uz')
    expect(pickStartLanguage(null, 'en')).toBe('ru')
  })

  it('defaults to ru; ignores garbage in storage', () => {
    expect(pickStartLanguage(null, null)).toBe('ru')
    expect(pickStartLanguage('de', 'uz')).toBe('uz')
  })
})

describe('rememberLanguage', () => {
  it('stores only ru/uz and survives a broken storage', () => {
    const s = memoryStorage()
    rememberLanguage(s, 'uz')
    expect(s.data[LAST_LANGUAGE_KEY]).toBe('uz')
    rememberLanguage(s, 'de')
    expect(s.data[LAST_LANGUAGE_KEY]).toBe('uz')
    expect(() =>
      rememberLanguage({ setItem: () => { throw new Error('x') } }, 'ru'),
    ).not.toThrow()
    expect(() => rememberLanguage(null, 'ru')).not.toThrow()
  })
})

describe('readTelegramLanguageCode', () => {
  it('reads language_code from tgWebAppData in the location hash', () => {
    const user = encodeURIComponent(JSON.stringify({ id: 1, language_code: 'uz' }))
    const hash = `#tgWebAppData=${encodeURIComponent(`user=${user}&auth_date=1`)}&tgWebAppVersion=8`
    expect(readTelegramLanguageCode(hash)).toBe('uz')
  })

  it('returns null for missing or broken data', () => {
    expect(readTelegramLanguageCode('')).toBeNull()
    expect(readTelegramLanguageCode('#tgWebAppData=user%3D%7Bbroken')).toBeNull()
  })
})
