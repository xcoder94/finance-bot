// QA m3-1: the inline script in index.html must pick the theme before first paint
// (dark by default, saved "light" respected, broken storage -> dark).
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { runInNewContext } from 'node:vm'
import { describe, expect, it } from 'vitest'

const html = readFileSync(resolve(__dirname, '../../index.html'), 'utf8')
const inline = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]).join('\n')

function prepaint(storage: { getItem: (k: string) => string | null }): string | undefined {
  const dataset: Record<string, string> = {}
  runInNewContext(inline, { localStorage: storage, document: { documentElement: { dataset } } })
  return dataset.theme
}

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
})
