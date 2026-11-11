import { describe, expect, it } from 'vitest'

// periodFilter.ts pulls in ../i18n, which touches `document.documentElement` at module
// load time; the vitest environment is `node`, so stub the minimal shape first.
;(globalThis as unknown as { document: { documentElement: { lang: string } } }).document ??= {
  documentElement: { lang: '' },
}

const { monthDateRange } = await import('../api/home')
const { dayEndIso, dayStartIso, tashkentDateOf } = await import('./dateChips')
const { initializeRangeFromMonth, resolveRange } = await import('./periodFilter')

const MONTH = { year: 2026, month: 8 }

describe('manual date range resolves Tashkent calendar boundaries', () => {
  it('resolves the start of 2026-08-01 to the Tashkent midnight instant', () => {
    expect(new Date(dayStartIso('2026-08-01')).toISOString()).toBe('2026-07-31T19:00:00.000Z')
  })

  it('resolves the end of 2026-08-31 to the Tashkent end-of-day instant', () => {
    expect(new Date(dayEndIso('2026-08-31')).toISOString()).toBe('2026-08-31T18:59:59.999Z')
  })

  it('produces byte-identical instants to monthDateRange for a whole-month range', () => {
    const { dateFrom, dateTo } = monthDateRange(2026, 8)
    expect(dayStartIso('2026-08-01')).toBe(dateFrom)
    expect(dayEndIso('2026-08-31')).toBe(dateTo)
  })

  it('includes an operation timestamped 02:00 Tashkent on 1 August in the range 08-01..08-31', () => {
    const { range } = resolveRange('range', MONTH, '2026-08-01', '2026-08-31')
    const operation = new Date('2026-07-31T21:00:00.000Z').getTime()
    expect(operation >= new Date(range!.dateFrom).getTime()).toBe(true)
    expect(operation <= new Date(range!.dateTo).getTime()).toBe(true)
  })
})

describe('resolveRange', () => {
  it('flags From later than To and returns no range', () => {
    expect(resolveRange('range', MONTH, '2026-08-10', '2026-08-01')).toEqual({
      range: null,
      rangeOrderInvalid: true,
    })
  })

  it('accepts a single-day range', () => {
    const { range, rangeOrderInvalid } = resolveRange('range', MONTH, '2026-08-05', '2026-08-05')
    expect(rangeOrderInvalid).toBe(false)
    expect(range).not.toBeNull()
  })

  it('returns no range and no order error while a date is empty', () => {
    expect(resolveRange('range', MONTH, '', '2026-08-05')).toEqual({
      range: null,
      rangeOrderInvalid: false,
    })
  })
})

describe('month -> manual range round trip (Tashkent calendar day)', () => {
  it('pre-fills the first and last day of a past month', () => {
    const { rangeFrom, rangeTo } = initializeRangeFromMonth(MONTH)
    expect(rangeFrom).toBe('2026-08-01')
    expect(rangeTo).toBe('2026-08-31')
  })

  it('round trips every month boundary of a past year', () => {
    for (let month = 1; month <= 12; month += 1) {
      const { rangeFrom } = initializeRangeFromMonth({ year: 2025, month })
      expect(rangeFrom).toBe(`2025-${String(month).padStart(2, '0')}-01`)
    }
  })

  it('clamps the end of a month that has not finished to today', () => {
    const now = new Date()
    const { rangeTo } = initializeRangeFromMonth({ year: now.getFullYear() + 1, month: 1 })
    expect(rangeTo <= tashkentDateOf(new Date())).toBe(true)
  })

  it('reads the Tashkent day, not the UTC day, for an instant that straddles midnight', () => {
    expect(tashkentDateOf('2026-07-31T21:00:00.000Z')).toBe('2026-08-01')
  })
})

describe('month -> range pre-fill never leaves the future (P1-3)', () => {
  it('a future month gives from = to = today, from never after to', () => {
    const today = tashkentDateOf(new Date())
    const next = new Date().getFullYear() + 1
    const { rangeFrom, rangeTo } = initializeRangeFromMonth({ year: next, month: 1 })
    expect(rangeFrom <= today).toBe(true)
    expect(rangeTo <= today).toBe(true)
    expect(rangeFrom <= rangeTo).toBe(true)
  })
})
