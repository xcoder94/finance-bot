import { afterEach, describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import i18n from '../i18n'

import { formatChartsEmptyMonth } from './analyticsChartsTab'
import { formatMonthLabel } from './periodFilter'

afterEach(async () => {
  await i18n.changeLanguage('ru')
})

describe('month labels case (P3-6)', () => {
  it('UZ: «2026-yil noyabr», no capitalised words', async () => {
    await i18n.changeLanguage('uz')
    expect(formatMonthLabel({ year: 2026, month: 11 })).toBe('2026-yil noyabr')
  })
  it('RU: first letter only, «г.» stays lower-case', async () => {
    await i18n.changeLanguage('ru')
    expect(formatMonthLabel({ year: 2026, month: 11 })).toBe('Ноябрь 2026 г.')
  })
  it('UZ empty-month sentence starts with a capital', async () => {
    await i18n.changeLanguage('uz')
    expect(formatChartsEmptyMonth({ year: 2026, month: 11 })).toBe('Noyabr')
  })
  it('RU empty-month keeps the lower-case month inside the sentence', async () => {
    await i18n.changeLanguage('ru')
    expect(formatChartsEmptyMonth({ year: 2026, month: 11 })).toBe('ноябрь')
  })
  it('no CSS text-transform: capitalize on month labels', () => {
    const css = readFileSync(join(__dirname, '..', 'index.css'), 'utf8')
    expect(css).not.toMatch(/text-transform:\s*capitalize/)
  })
})
