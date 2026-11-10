import { describe, expect, it } from 'vitest'

import ru from './locales/ru.json'
import uz from './locales/uz.json'

type Tree = { [key: string]: string | Tree }

function flatten(tree: Tree, prefix = ''): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(tree)) {
    if (typeof value === 'string') out[prefix + key] = value
    else Object.assign(out, flatten(value, `${prefix}${key}.`))
  }
  return out
}

const ruFlat = flatten(ru as Tree)
const uzFlat = flatten(uz as Tree)
const placeholders = (s: string) => [...s.matchAll(/\{\{\s*([\w.]+)\s*(?:,[^}]*)?\}\}/g)].map((m) => m[1]).sort()
// UZ has no grammatical plural: only the _other form is required for plural keys.
const isRuOnlyPlural = (key: string) => /_(zero|one|two|few|many)$/.test(key)

describe('RU/UZ key parity (U6)', () => {
  it('every RU key has a non-empty UZ value', () => {
    const missing = Object.keys(ruFlat)
      .filter((k) => !isRuOnlyPlural(k))
      .filter((k) => !(uzFlat[k] ?? '').trim())
    expect(missing).toEqual([])
  })

  it('no UZ value is empty', () => {
    expect(Object.entries(uzFlat).filter(([, v]) => !v.trim()).map(([k]) => k)).toEqual([])
  })

  it('UZ uses only the ASCII apostrophe', () => {
    expect(Object.entries(uzFlat).filter(([, v]) => /[‘’ʻʼ`´]/.test(v)).map(([k]) => k)).toEqual([])
  })

  it('UZ placeholders match RU placeholders', () => {
    const bad: string[] = []
    for (const [key, uzValue] of Object.entries(uzFlat)) {
      const ruValue = ruFlat[key] ?? ruFlat[key.replace(/_other$/, '_many')]
      if (ruValue === undefined) continue
      const a = placeholders(ruValue)
      const b = placeholders(uzValue)
      if (JSON.stringify(a) !== JSON.stringify(b)) bad.push(`${key}: ${a} vs ${b}`)
    }
    expect(bad).toEqual([])
  })
})
