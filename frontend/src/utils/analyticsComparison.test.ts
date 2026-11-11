import { afterEach, describe, expect, it } from 'vitest'

import i18n from '../i18n'
import {
  buildComparisonLine,
  buildHeadline,
  deltaLabel,
  donutCenterFontSize,
  formatSharePercent,
  rangeLengthDays,
} from './analyticsComparison'

const RU_PREP = [
  'январе', 'феврале', 'марте', 'апреле', 'мае', 'июне',
  'июле', 'августе', 'сентябре', 'октябре', 'ноябре', 'декабре',
]

describe('headline comparison line (RU)', () => {
  afterEach(async () => {
    await i18n.changeLanguage('ru')
  })

  it('uses the correct prepositional form of the previous month for all 12 months', () => {
    for (let month = 1; month <= 12; month += 1) {
      const prev = month === 1 ? 12 : month - 1
      const line = buildComparisonLine({
        total: 2000,
        prevTotal: 1000,
        periodTab: 'month',
        selectedMonth: { year: 2026, month },
        rangeDays: 30,
      })
      expect(line).toBe(`на 100% больше, чем в ${RU_PREP[prev - 1]}`)
    }
  })

  it('more / less / same wording for 1 000 000 vs 1 120 000', () => {
    const base = { periodTab: 'month' as const, selectedMonth: { year: 2026, month: 11 }, rangeDays: 30 }
    expect(buildComparisonLine({ ...base, total: 1_120_000, prevTotal: 1_000_000 })).toBe(
      'на 12% больше, чем в октябре',
    )
    expect(buildComparisonLine({ ...base, total: 880_000, prevTotal: 1_000_000 })).toBe(
      'на 12% меньше, чем в октябре',
    )
    expect(buildComparisonLine({ ...base, total: 1_000_000, prevTotal: 1_000_000 })).toBe(
      'столько же, как в октябре',
    )
  })

  it('is hidden when the previous period has no expenses', () => {
    expect(
      buildComparisonLine({
        total: 500,
        prevTotal: 0,
        periodTab: 'month',
        selectedMonth: { year: 2026, month: 11 },
        rangeDays: 30,
      }),
    ).toBeNull()
  })

  it('custom range compares to the previous N days', () => {
    expect(
      buildComparisonLine({
        total: 1120,
        prevTotal: 1000,
        periodTab: 'range',
        selectedMonth: { year: 2026, month: 11 },
        rangeDays: 30,
      }),
    ).toBe('на 12% больше, чем за прошлые 30 дней')
  })

  it('headline has the month and the amount', () => {
    expect(buildHeadline({ periodTab: 'month', selectedMonth: { year: 2026, month: 11 }, amount: '4 200 000 сум' })).toBe(
      'Расход за ноябрь: 4 200 000 сум',
    )
  })

  it('Uzbek lines exist and have no Cyrillic', async () => {
    await i18n.changeLanguage('uz')
    const line = buildComparisonLine({
      total: 1120,
      prevTotal: 1000,
      periodTab: 'month',
      selectedMonth: { year: 2026, month: 11 },
      rangeDays: 30,
    })
    expect(line).toMatch(/12%/)
    expect(line).not.toMatch(/[А-Яа-я]/)
  })
})

describe('deltaLabel', () => {
  afterEach(async () => {
    await i18n.changeLanguage('ru')
  })

  it('shows новая when absent last period', () => {
    expect(deltaLabel(500, 0)).toEqual({ kind: 'new', text: 'новая' })
  })
  it('signed percent with a real minus', () => {
    expect(deltaLabel(112, 100)).toEqual({ kind: 'up', text: '+12%' })
    expect(deltaLabel(95, 100)).toEqual({ kind: 'down', text: '−5%' })
    expect(deltaLabel(100, 100)).toEqual({ kind: 'same', text: '0%' })
  })
})

describe('helpers', () => {
  it('rangeLengthDays rounds the inclusive length', () => {
    expect(rangeLengthDays('2026-11-01T00:00:00+05:00', '2026-11-30T23:59:59.999+05:00')).toBe(30)
  })
  it('formatSharePercent trims integers and keeps one decimal', () => {
    expect(formatSharePercent(40)).toBe('40%')
    expect(formatSharePercent(33.3)).toBe('33,3%')
  })
  it('centre amount shrinks to fit the ring', () => {
    const short = donutCenterFontSize('120 000', 120)
    const long = donutCenterFontSize('2 002 658 999', 120)
    expect(long).toBeLessThan(short)
    expect(long * 0.62 * '2 002 658 999'.length).toBeLessThanOrEqual(120)
    expect(donutCenterFontSize('1', 120)).toBeLessThanOrEqual(22)
    expect(donutCenterFontSize('9 999 999 999 999', 100)).toBeGreaterThanOrEqual(9)
  })
})

describe('range comparison label counts the PREVIOUS period (QA #8)', () => {
  it('Oct 1-31 vs September (30 days): «за прошлые 30 дней», not 31', () => {
    const days = rangeLengthDays('2026-09-01T00:00:00+05:00', '2026-09-30T23:59:59.999+05:00')
    expect(days).toBe(30)
    const line = buildComparisonLine({
      total: 120,
      prevTotal: 100,
      periodTab: 'range',
      selectedMonth: { year: 2026, month: 10 },
      rangeDays: days,
    })
    expect(line).toContain('30')
    expect(line).not.toContain('31')
  })
})
