import { describe, expect, it, vi } from 'vitest'

import { stubIntlWithoutUzbekMonths } from '../test/noUzbekIntl'

import {
  addDays,
  chipKeyFor,
  clampPickedDate,
  dateToTransactionIso,
  dayEndIso,
  dayStartIso,
  formatChipDate,
  isSelectableDate,
  isValidIsoDate,
  presetRange,
  tashkentDateOf,
  todayTashkent,
} from './dateChips'

describe('todayTashkent', () => {
  it('uses the Tashkent calendar day, not the host day', () => {
    // 20:00 UTC on 9 Nov is already 01:00 on 10 Nov in Tashkent
    expect(todayTashkent(new Date('2026-11-09T20:00:00Z'))).toBe('2026-11-10')
    expect(todayTashkent(new Date('2026-11-09T18:59:00Z'))).toBe('2026-11-09')
  })
})

describe('addDays', () => {
  it('crosses month and year boundaries', () => {
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28')
    expect(addDays('2028-03-01', -1)).toBe('2028-02-29')
    expect(addDays('2026-01-01', -1)).toBe('2025-12-31')
    expect(addDays('2025-12-31', 1)).toBe('2026-01-01')
  })
})

describe('validation', () => {
  it('rejects malformed and impossible dates', () => {
    expect(isValidIsoDate('2026-02-30')).toBe(false)
    expect(isValidIsoDate('')).toBe(false)
    expect(isValidIsoDate('10.11.2026')).toBe(false)
    expect(isValidIsoDate('2026-11-10')).toBe(true)
  })
  it('does not allow a future day (tomorrow in Tashkent)', () => {
    expect(isSelectableDate('2026-11-11', '2026-11-10')).toBe(false)
    expect(isSelectableDate('2026-11-10', '2026-11-10')).toBe(true)
    expect(isSelectableDate('', '2026-11-10')).toBe(false)
  })
})

describe('chipKeyFor', () => {
  it('maps the stored day to a chip', () => {
    const today = '2026-11-10'
    expect(chipKeyFor('2026-11-10', today)).toBe('today')
    expect(chipKeyFor('2026-11-09', today)).toBe('yesterday')
    expect(chipKeyFor('2026-11-08', today)).toBe('dayBefore')
    expect(chipKeyFor('2026-11-07', today)).toBe('other')
  })
  it('works across a month boundary', () => {
    expect(chipKeyFor('2026-10-31', '2026-11-01')).toBe('yesterday')
    expect(chipKeyFor('2026-10-30', '2026-11-01')).toBe('dayBefore')
  })
})

describe('formatChipDate', () => {
  it('omits the year for the current year', () => {
    expect(formatChipDate('2026-11-08', '2026-11-10', 'ru-RU')).toBe('8 ноября')
  })
  it('adds the year otherwise, without the trailing «г.»', () => {
    expect(formatChipDate('2025-11-08', '2026-11-10', 'ru-RU')).toBe('8 ноября 2025')
  })
})

describe('dateToTransactionIso', () => {
  it('new record: noon Tashkent of the chosen day', () => {
    expect(dateToTransactionIso('2026-11-09')).toBe('2026-11-09T12:00:00.000+05:00')
  })
  it('edit: keeps the original Tashkent time of day', () => {
    // 23:30:15.250 Tashkent on 7 Nov == 18:30:15.250 UTC
    const original = '2026-11-07T18:30:15.250Z'
    const next = dateToTransactionIso('2026-11-09', original)
    expect(next).toBe('2026-11-09T23:30:15.250+05:00')
    expect(new Date(next as string).toISOString()).toBe('2026-11-09T18:30:15.250Z')
  })
  it('edit with the same day returns the same instant', () => {
    const original = '2026-11-07T18:30:15.250Z'
    const next = dateToTransactionIso('2026-11-08', original)
    expect(new Date(next as string).toISOString()).toBe('2026-11-08T18:30:15.250Z')
  })
  it('returns null for an invalid date', () => {
    expect(dateToTransactionIso('nope')).toBeNull()
  })
})

describe('tashkentDateOf', () => {
  it('reads the Tashkent day of an instant', () => {
    expect(tashkentDateOf('2026-07-31T21:00:00.000Z')).toBe('2026-08-01')
    expect(tashkentDateOf('2026-07-31T18:59:00.000Z')).toBe('2026-07-31')
  })
})

describe('day boundaries', () => {
  it('start and end of a Tashkent day', () => {
    expect(new Date(dayStartIso('2026-08-01')).toISOString()).toBe('2026-07-31T19:00:00.000Z')
    expect(new Date(dayEndIso('2026-08-31')).toISOString()).toBe('2026-08-31T18:59:59.999Z')
  })
})

describe('presetRange', () => {
  it('7 days and 30 days end today and include it', () => {
    expect(presetRange('days7', '2026-11-10')).toEqual({ from: '2026-11-04', to: '2026-11-10' })
    expect(presetRange('days30', '2026-11-10')).toEqual({ from: '2026-10-12', to: '2026-11-10' })
  })
  it('this month: first of the month to today', () => {
    expect(presetRange('thisMonth', '2026-11-10')).toEqual({ from: '2026-11-01', to: '2026-11-10' })
  })
  it('last month on 10 Nov is 1-31 Oct', () => {
    expect(presetRange('lastMonth', '2026-11-10')).toEqual({ from: '2026-10-01', to: '2026-10-31' })
  })
  it('last month across a year boundary and in February', () => {
    expect(presetRange('lastMonth', '2026-01-15')).toEqual({ from: '2025-12-01', to: '2025-12-31' })
    expect(presetRange('lastMonth', '2028-03-02')).toEqual({ from: '2028-02-01', to: '2028-02-29' })
  })
  it('7 days across a year boundary', () => {
    expect(presetRange('days7', '2026-01-03')).toEqual({ from: '2025-12-28', to: '2026-01-03' })
  })
})

describe('formatChipDate in Uzbek (own month names, never Intl) (P1-1)', () => {
  it('current year: «7-noyabr»; other year: «2025-yil 8-noyabr»', () => {
    expect(formatChipDate('2026-11-07', '2026-11-10', 'uz-UZ')).toBe('7-noyabr')
    expect(formatChipDate('2025-11-08', '2026-11-10', 'uz-UZ')).toBe('2025-yil 8-noyabr')
    expect(formatChipDate('2026-01-01', '2026-11-10', 'uz-UZ')).toBe('1-yanvar')
  })
  it('never prints the Intl fallback «M11» on a device whose Intl has no Uzbek months', () => {
    stubIntlWithoutUzbekMonths()
    try {
      expect(formatChipDate('2026-11-07', '2026-11-10', 'uz-UZ')).toBe('7-noyabr')
      expect(formatChipDate('2025-12-08', '2026-11-10', 'uz-UZ')).toBe('2025-yil 8-dekabr')
    } finally {
      vi.unstubAllGlobals()
    }
  })
})

describe('clampPickedDate (P1-6: a future day from the iOS wheel is not dropped silently)', () => {
  it('keeps an allowed day', () => {
    expect(clampPickedDate('2026-11-08', '2026-11-10')).toBe('2026-11-08')
  })
  it('pulls a future day to today', () => {
    expect(clampPickedDate('2026-11-11', '2026-11-10')).toBe('2026-11-10')
  })
  it('pulls a day before min to min', () => {
    expect(clampPickedDate('2026-11-01', '2026-11-10', '2026-11-05')).toBe('2026-11-05')
  })
  it('rejects garbage', () => {
    expect(clampPickedDate('', '2026-11-10')).toBeNull()
  })
})
