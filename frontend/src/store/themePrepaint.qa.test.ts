// QA m3-1: the inline script in index.html must pick the theme before first paint
// (dark by default, saved "light" respected, broken storage -> dark).
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { runInNewContext } from 'node:vm'
import { describe, expect, it } from 'vitest'

const html = readFileSync(resolve(__dirname, '../../index.html'), 'utf8')
const inline = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]).join('\n')

type Env = {
  hash?: string
  colorScheme?: string
  media?: 'dark' | 'light'
  session?: string
}

function prepaint(storage: { getItem: (k: string) => string | null }, env: Env = {}): string | undefined {
  const dataset: Record<string, string> = {}
  runInNewContext(inline, {
    localStorage: storage,
    sessionStorage: { getItem: () => env.session ?? null },
    location: { hash: env.hash ?? '' },
    URLSearchParams,
    JSON,
    window: {
      Telegram: env.colorScheme ? { WebApp: { colorScheme: env.colorScheme } } : undefined,
      matchMedia: env.media ? () => ({ matches: env.media === 'dark' }) : undefined,
    },
    document: { documentElement: { dataset } },
  })
  return dataset.theme
}

const launch = (bg: string) => `tgWebAppThemeParams=${encodeURIComponent(JSON.stringify({ bg_color: bg }))}`

describe('index.html pre-paint theme script', () => {
  it('exists in <head> before the app bundle', () => {
    expect(inline).toContain('app-theme')
    expect(html.indexOf(inline)).toBeLessThan(html.indexOf('/src/main.tsx'))
  })
  it('first launch (nothing saved) -> dark', () => {
    expect(prepaint({ getItem: () => null })).toBe('dark')
  })
  it('saved light -> light', () => {
    expect(prepaint({ getItem: (k) => (k === 'app-theme' ? 'light' : null) })).toBe('light')
  })
  it('garbage -> dark', () => {
    expect(prepaint({ getItem: () => 'purple' })).toBe('dark')
  })
  it('storage throws -> dark', () => {
    expect(prepaint({ getItem: () => { throw new Error('denied') } })).toBe('dark')
  })
  it('System (nothing saved): Telegram colorScheme light -> light, dark -> dark', () => {
    expect(prepaint({ getItem: () => null }, { colorScheme: 'light' })).toBe('light')
    expect(prepaint({ getItem: () => null }, { colorScheme: 'dark' })).toBe('dark')
  })
  it('System: launch params in the URL hash (real Telegram) decide the first frame', () => {
    expect(prepaint({ getItem: () => null }, { hash: `#tgWebAppVersion=8&${launch('#ffffff')}` })).toBe('light')
    expect(prepaint({ getItem: () => null }, { hash: `#${launch('#17212b')}` })).toBe('dark')
    expect(prepaint({ getItem: () => null }, { session: launch('#ffffff') })).toBe('light')
  })
  it('System outside Telegram follows prefers-color-scheme', () => {
    expect(prepaint({ getItem: () => null }, { media: 'light' })).toBe('light')
    expect(prepaint({ getItem: () => null }, { media: 'dark' })).toBe('dark')
  })
  it('saved "system" behaves like nothing saved', () => {
    expect(prepaint({ getItem: () => 'system' }, { colorScheme: 'light' })).toBe('light')
  })
  it('an explicit choice beats Telegram', () => {
    expect(prepaint({ getItem: () => 'dark' }, { colorScheme: 'light' })).toBe('dark')
    expect(prepaint({ getItem: () => 'light' }, { colorScheme: 'dark' })).toBe('light')
  })
})
