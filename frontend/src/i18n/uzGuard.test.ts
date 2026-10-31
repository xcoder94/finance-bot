import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

import { describe, expect, it } from 'vitest'

import ru from './locales/ru.json'
import uz from './locales/uz.json'

type Tree = { [key: string]: string | Tree }

const CYRILLIC = /[Ѐ-ӿ]/
/** The single UZ apostrophe: ASCII ' (decision of the m3-5 task; swap mechanically if the owner picks another). */
const FOREIGN_APOSTROPHES = /[‘’ʻʼ`´]/
const PLURAL_SUFFIX = /_(zero|one|two|few|many|other)$/

function flatten(tree: Tree, prefix = ''): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [key, value] of Object.entries(tree)) {
    if (typeof value === 'string') {
      out[prefix + key] = value
    } else {
      Object.assign(out, flatten(value, `${prefix}${key}.`))
    }
  }
  return out
}

const ruFlat = flatten(ru as Tree)
const uzFlat = flatten(uz as Tree)
const base = (key: string) => key.replace(PLURAL_SUFFIX, '')

/** uz.json values that may legitimately contain Cyrillic (user data placeholders etc.). */
const CYRILLIC_ALLOWED_UZ_KEYS = new Set<string>([])

describe('uz.json guard', () => {
  it('has no Cyrillic outside the allow-list', () => {
    const offenders = Object.entries(uzFlat)
      .filter(([key, value]) => CYRILLIC.test(value) && !CYRILLIC_ALLOWED_UZ_KEYS.has(key))
      .map(([key, value]) => `${key}: ${value}`)
    expect(offenders).toEqual([])
  })

  it('uses one apostrophe style (ASCII) everywhere', () => {
    const offenders = Object.entries(uzFlat)
      .filter(([, value]) => FOREIGN_APOSTROPHES.test(value))
      .map(([key]) => key)
    expect(offenders).toEqual([])
  })

  it('has the same keys as ru.json (plural forms compared by base key)', () => {
    const ruBases = new Set(Object.keys(ruFlat).map(base))
    const uzBases = new Set(Object.keys(uzFlat).map(base))
    expect([...ruBases].filter((k) => !uzBases.has(k))).toEqual([])
    expect([...uzBases].filter((k) => !ruBases.has(k))).toEqual([])
  })

  it('has an _other form for every plural key (UZ has no grammatical plural)', () => {
    const pluralBases = new Set(
      Object.keys(uzFlat)
        .filter((k) => PLURAL_SUFFIX.test(k))
        .map(base),
    )
    const missing = [...pluralBases].filter((b) => !(`${b}_other` in uzFlat))
    expect(missing).toEqual([])
  })

  it('does not copy Russian text into uz.json', () => {
    const same = Object.entries(uzFlat)
      .filter(([key, value]) => ruFlat[key] === value && /[a-zA-ZЀ-ӿ]{3}/.test(value))
      .map(([key, value]) => `${key}: ${value}`)
    expect(same).toEqual([])
  })
})

/**
 * Cyrillic that may stay in source, matched per LINE (trimmed) - never a whole file.
 * A new Cyrillic literal anywhere (also in an allow-listed file) fails the guard.
 */
const LINE_ALLOW: Record<string, RegExp[]> = {
  // keyword tables matched against user-entered category names (user data)
  'components/settings/expenseCategoryIcon.ts': [/^\['[а-яё]+', [A-Za-z]+\],$/],
  'components/settings/incomeCategoryIcon.ts': [/^\['[а-яё]+', [A-Za-z]+\],$/],
  // backend-seeded default category name, compared as data
  'utils/transactionFormFields.ts': [/^export const UNCATEGORIZED_CATEGORY_NAME = 'Без категории'$/],
  // endonym of the language, always shown in its own language
  'pages/settings/LanguageSettingsPage.tsx': [/^\{ code: 'ru', label: 'Русский' \},$/],
  'utils/settingsSubtitles.ts': [
    /^return language\.startsWith\('uz'\) \? "O'zbekcha" : 'Русский'$/,
  ],
}

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name)
    if (statSync(full).isDirectory()) return walk(full)
    return /\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [full] : []
  })
}

/** Chars after which a `/` starts a regex literal (not division). */
const REGEX_PREV = new Set(['', '(', ',', '=', ':', '[', '!', '&', '|', '?', '{', '}', ';', '+', '-', '*', '%', '<', '>', '~', '^'])
/**
 * `//` is a comment only at line start or right after code that ends a statement/argument.
 * After letters, digits or `>` it may be JSX text or a URL, so it is NOT trusted to hide Cyrillic.
 */
const COMMENT_PREV = new Set(['', ';', ',', '{', '}', '(', ')', ']', "'", '"', '`'])

/**
 * Drops comments with a tiny lexer that knows string/template literals and regex literals,
 * so a `//` or `/*` INSIDE them (or in JSX text) does not hide the rest of the line.
 */
export function stripComments(source: string): string {
  let out = ''
  let i = 0
  let quote: string | null = null
  let prev = '' // last non-space char on the current line
  while (i < source.length) {
    const c = source[i]
    const next = source[i + 1]
    if (quote) {
      out += c
      if (c === '\\') {
        out += next ?? ''
        i += 2
        continue
      }
      if (c === quote || (c === '\n' && quote !== '`')) {
        quote = null
        prev = c === '\n' ? '' : c
      }
      i += 1
    } else if (c === '/' && next === '/' && COMMENT_PREV.has(prev)) {
      while (i < source.length && source[i] !== '\n') i += 1
    } else if (c === '/' && next === '*') {
      const end = source.indexOf('*/', i + 2)
      const stop = end === -1 ? source.length : end + 2
      out += source.slice(i, stop).replace(/[^\n]/g, '')
      i = stop
    } else if (c === '/' && REGEX_PREV.has(prev)) {
      // regex literal: copy up to the closing unescaped `/` (a `/` inside [...] does not close it)
      let j = i + 1
      let inClass = false
      while (j < source.length && source[j] !== '\n') {
        if (source[j] === '\\') j += 1
        else if (source[j] === '[') inClass = true
        else if (source[j] === ']') inClass = false
        else if (source[j] === '/' && !inClass) break
        j += 1
      }
      out += source.slice(i, j + 1)
      i = j + 1
      prev = '/'
    } else {
      if (c === '"' || c === "'" || c === '`') quote = c
      out += c
      if (c === '\n') prev = ''
      else if (c !== ' ' && c !== '\t') prev = c
      i += 1
    }
  }
  return out
}

/** Non-comment lines with Cyrillic that no per-line allow rule covers. */
export function cyrillicOffenders(rel: string, source: string): string[] {
  const allowed = LINE_ALLOW[rel] ?? []
  return stripComments(source)
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => CYRILLIC.test(line) && !allowed.some((rule) => rule.test(line)))
}

describe('no hard-coded Russian in src', () => {
  it('has no Cyrillic literals except the per-line allow-list', () => {
    const srcRoot = join(__dirname, '..')
    const offenders = walk(srcRoot).flatMap((file) => {
      const rel = relative(srcRoot, file)
      return cyrillicOffenders(rel, readFileSync(join(srcRoot, rel), 'utf8')).map(
        (line) => `${rel}: ${line}`,
      )
    })
    expect(offenders).toEqual([])
  })

  it('catches a Russian heading in an allow-listed file (mutant)', () => {
    const file = "  { code: 'ru', label: 'Русский' },\n  <h1>Язык интерфейса</h1>\n"
    expect(cyrillicOffenders('pages/settings/LanguageSettingsPage.tsx', file)).toEqual([
      '<h1>Язык интерфейса</h1>',
    ])
  })

  it('catches Cyrillic after // inside a string literal (mutant)', () => {
    expect(cyrillicOffenders('x.ts', `const a = '// Кириллица'`)).toHaveLength(1)
    expect(cyrillicOffenders('x.ts', 'const a = "http://x" + \'Привет\'')).toHaveLength(1)
    expect(cyrillicOffenders('x.ts', 'const a = `// Кириллица`')).toHaveLength(1)
  })

  it('catches Cyrillic in an allow-listed file when the line differs (mutant)', () => {
    expect(cyrillicOffenders('utils/settingsSubtitles.ts', "return 'Русский'")).toHaveLength(1)
    expect(cyrillicOffenders('components/settings/incomeCategoryIcon.ts', "['новое слово', X],")).toHaveLength(1)
  })

  it('catches Cyrillic after // in a regex literal or JSX text (mutant)', () => {
    expect(cyrillicOffenders('x.ts', 'const r = /\\/\\/ Привет/')).toHaveLength(1)
    expect(cyrillicOffenders('x.ts', 'const r = x.replace(/\\/\\//g, "") + \'Привет\'')).toHaveLength(1)
    expect(cyrillicOffenders('x.tsx', '<p>http://a // Привет</p>')).toHaveLength(1)
    expect(cyrillicOffenders('x.tsx', '<a href="x">// Привет</a>')).toHaveLength(1)
  })

  it('still ignores trailing comments after code', () => {
    expect(cyrillicOffenders('x.ts', 'foo(1) // Привет')).toEqual([])
    expect(cyrillicOffenders('x.ts', 'const a = 1; // Привет')).toEqual([])
    expect(cyrillicOffenders('x.ts', '  } // Привет')).toEqual([])
  })

  it('still ignores real comments', () => {
    const src = '// Кириллица\n/* и тут\n тоже */\nconst a = 1; // и здесь\n'
    expect(cyrillicOffenders('x.ts', src)).toEqual([])
  })
})
