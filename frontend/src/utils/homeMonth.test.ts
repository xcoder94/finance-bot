import { afterEach, describe, expect, it, vi } from 'vitest'

import i18n from '../i18n'
import {
  balanceMonthLabel,
  currentMonthInTashkent,
  emptyMonthTitle,
  formatMonthTitle,
  monthShortLabel,
  opsCountLabel,
  shiftHomeMonth,
} from './homeMonth'

const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)

describe('month short labels', () => {
  afterEach(async () => {
    await i18n.changeLanguage('ru')
  })

  it('has 12 Russian short month labels', () => {
    expect(MONTHS.map(monthShortLabel)).toEqual([
      'янв', 'фев', 'март', 'апр', 'май', 'июнь', 'июль', 'август', 'сен', 'окт', 'ноя', 'дек',
    ])
  })

  it('has 12 Uzbek short month labels, no Cyrillic', async () => {
    await i18n.changeLanguage('uz')
    expect(MONTHS.map(monthShortLabel)).toEqual([
      'yan', 'fev', 'mart', 'apr', 'may', 'iyun', 'iyul', 'avgust', 'sen', 'okt', 'noy', 'dek',
    ])
  })
})

describe('month titles and empty-month phrase', () => {
  afterEach(async () => {
    await i18n.changeLanguage('ru')
  })

  it('Russian: prepositional month in the empty title', () => {
    expect(emptyMonthTitle(8)).toBe('В августе операций нет')
    expect(opsCountLabel(0, 8)).toBe('нет операций')
  })

  it('Uzbek: locative month, "2026-yil avgust" title, Qoldiq label', async () => {
    await i18n.changeLanguage('uz')
    expect(emptyMonthTitle(8)).toBe("Avgustda operatsiyalar yo'q")
    expect(formatMonthTitle(2026, 8)).toBe('2026-yil avgust')
    expect(balanceMonthLabel(10)).toBe('Oy yakuni · okt')
    expect(opsCountLabel(0, 8)).toBe("operatsiyalar yo'q")
  })
})

describe('monthShortLabel', () => {
  it('returns short label for valid month', () => {
    expect(monthShortLabel(8)).toBe('август')
  })
})

describe('emptyMonthTitle', () => {
  it('formats empty month title with prepositional month', () => {
    expect(emptyMonthTitle(8)).toBe('В августе операций нет')
  })
})

describe('opsCountLabel', () => {
  it('returns none label when count is zero', () => {
    expect(opsCountLabel(0, 8)).toBe('нет операций')
  })

  it('returns count with short month when count is positive', () => {
    expect(opsCountLabel(32, 8)).toBe('32 за август')
  })
})

describe('balanceMonthLabel', () => {
  it('formats balance label with short month', () => {
    expect(balanceMonthLabel(8)).toBe('Итог месяца · август')
  })
})

describe('formatMonthTitle', () => {
  it('formats nominative long month with year', () => {
    expect(formatMonthTitle(2026, 8)).toBe('Август 2026')
  })
})

describe('currentMonthInTashkent', () => {
  it('returns year and month in Asia/Tashkent', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-03T20:30:00.000Z'))

    expect(currentMonthInTashkent()).toEqual({ year: 2026, month: 8 })

    vi.useRealTimers()
  })
})

describe('shiftHomeMonth', () => {
  it('shifts month forward and backward', () => {
    expect(shiftHomeMonth({ year: 2026, month: 12 }, 1)).toEqual({ year: 2027, month: 1 })
    expect(shiftHomeMonth({ year: 2026, month: 1 }, -1)).toEqual({ year: 2025, month: 12 })
  })
})
