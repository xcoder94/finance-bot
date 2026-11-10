import { execFileSync } from 'node:child_process'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

import ru from './i18n/locales/ru.json'
import uz from './i18n/locales/uz.json'

const srcDir = __dirname

function grep(pattern: string): string {
  try {
    return execFileSync('git', ['grep', '-n', '-F', pattern, '--', srcDir], {
      cwd: join(srcDir, '..'),
      encoding: 'utf8',
    })
  } catch {
    return ''
  }
}

// B19: developer texts must not live in the UI
describe('developer texts are gone (B19)', () => {
  for (const text of [
    'Валюты совпадают',
    'Каждая сущность настраивается',
    'Свайп влево открывает',
    'transferSameIntro',
    'toc.footerHint',
  ]) {
    it(`no «${text}» in src or locales`, () => {
      expect(grep(text).replace(/devTextsRemoved\.test\.ts.*\n?/g, '')).toBe('')
    })
  }
  it('uz locale has no swipe hint either', () => {
    expect(JSON.stringify(uz)).not.toContain('Chapga suring')
    expect(JSON.stringify(ru)).not.toContain('Свайп')
  })
})

// B18: one retry text everywhere
describe('one retry text (B18)', () => {
  it('«Повторить» is not used as a button label any more', () => {
    expect((ru as { home: Record<string, unknown> }).home.retry).toBeUndefined()
    expect(ru.auth.retry).toBe('Попробовать снова')
  })
})
