import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import ru from './locales/ru.json'
import uz from './locales/uz.json'

type Tree = { [key: string]: string | Tree }

/** Prefixes whose keys are built at runtime (t(`prefix.${x}`)): data-driven, checked by their own tests. */
const DYNAMIC_PREFIXES = ['defaultEntities.', 'months.', 'dateChips.', 'tabs.', 'ops.', 'settings.roles.', 'analytics.compactUnits.']
const PLURAL_SUFFIX = /_(zero|one|two|few|many|other)$/

function flatten(tree: Tree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([k, v]) => (typeof v === 'string' ? [prefix + k] : flatten(v, `${prefix}${k}.`)))
}

function sources(dir: string): string[] {
  const out: string[] = []
  for (const name of readdirSync(dir)) {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) out.push(...sources(path))
    else if (/\.(ts|tsx)$/.test(name) && !/\.test\.(ts|tsx)$/.test(name)) out.push(readFileSync(path, 'utf8'))
  }
  return out
}

describe('locale keys are used', () => {
  const code = sources(join(__dirname, '..')).join('\n')
  const bases = [...new Set(flatten(ru as Tree).map((k) => k.replace(PLURAL_SUFFIX, '')))]

  it('no ru.json key is unreferenced in src', () => {
    const unused = bases.filter((k) => !DYNAMIC_PREFIXES.some((p) => k.startsWith(p))).filter((k) => !code.includes(k))
    expect(unused).toEqual([])
  })

  it('uz.json has no keys beyond ru.json', () => {
    const ruBases = new Set(bases)
    const extra = [...new Set(flatten(uz as Tree).map((k) => k.replace(PLURAL_SUFFIX, '')))].filter((k) => !ruBases.has(k))
    expect(extra).toEqual([])
  })
})
