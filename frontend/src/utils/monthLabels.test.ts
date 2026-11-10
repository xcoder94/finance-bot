import { afterEach, describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import i18n from '../i18n'

import { formatChartsEmptyMonth } from './analyticsChartsTab'
import { formatMonthTitle } from './homeMonth'
import { formatMonthLabel, formatShortMonthKey } from './periodFilter'

afterEach(async () => {
  await i18n.changeLanguage('ru')
})

describe('month labels case (P3-6)', () => {
  it('UZ: «2026-yil noyabr», no capitalised words', async () => {
    await i18n.changeLanguage('uz')
    expect(formatMonthLabel({ year: 2026, month: 11 })).toBe('2026-yil noyabr')
  })
  it('RU: «Ноябрь 2026», no «г.» (B21)', async () => {
    await i18n.changeLanguage('ru')
    expect(formatMonthLabel({ year: 2026, month: 11 })).toBe('Ноябрь 2026')
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
  it('one helper: Home title equals the shared label, RU and UZ (B21)', async () => {
    for (const lng of ['ru', 'uz']) {
      await i18n.changeLanguage(lng)
      expect(formatMonthLabel({ year: 2026, month: 11 })).toBe(formatMonthTitle(2026, 11))
      expect(formatMonthLabel({ year: 2026, month: 11 })).not.toMatch(/г\./)
    }
  })
  it('UZ short month keys come from app strings: Noy / Dek, never M12 (B6)', async () => {
    await i18n.changeLanguage('uz')
    expect(formatShortMonthKey('2026-11')).toBe('Noy')
    expect(formatShortMonthKey('2026-12')).toBe('Dek')
    expect(formatShortMonthKey('2026-01')).not.toMatch(/^M\d+$/)
  })
  it('RU short month key', async () => {
    await i18n.changeLanguage('ru')
    expect(formatShortMonthKey('2026-11')).toBe('Ноя')
  })
})
