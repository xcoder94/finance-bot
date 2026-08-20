import { describe, expect, it } from 'vitest'

// transactionForm.ts pulls in formatCurrency -> ../i18n, which touches
// `document.documentElement` at module load time. The vitest environment for
// this suite is `node` (see vitest.config.ts), so stub the minimal shape
// `../i18n` needs before importing anything that transitively loads it.
;(globalThis as unknown as { document: { documentElement: { lang: string } } }).document ??= {
  documentElement: { lang: '' },
}

const { monthDateRange } = await import('../api/home')
const { maskedDateToUtcEndIso, maskedDateToUtcStartIso, isoDateToMaskedDate } = await import('./transactionForm')
const { initializeRangeFromMonth } = await import('./periodFilter')

describe('manual date range resolves Tashkent calendar boundaries', () => {
  it('resolves the start of 01.08.2026 to the Tashkent midnight instant', () => {
    const start = maskedDateToUtcStartIso('01.08.2026')
    expect(start).not.toBeNull()
    expect(new Date(start as string).toISOString()).toBe('2026-07-31T19:00:00.000Z')
  })

  it('resolves the end of 31.08.2026 to the Tashkent end-of-day instant', () => {
    const end = maskedDateToUtcEndIso('31.08.2026')
    expect(end).not.toBeNull()
    expect(new Date(end as string).toISOString()).toBe('2026-08-31T18:59:59.999Z')
  })

  it('produces byte-identical instants to monthDateRange for a whole-month range', () => {
    const { dateFrom, dateTo } = monthDateRange(2026, 8)

    const rangeFrom = maskedDateToUtcStartIso('01.08.2026')
    const rangeTo = maskedDateToUtcEndIso('31.08.2026')

    expect(rangeFrom).toBe(dateFrom)
    expect(rangeTo).toBe(dateTo)
  })

  it('includes an operation timestamped 02:00 Tashkent on 1 August in the manual range 01.08-31.08', () => {
    const dateFrom = maskedDateToUtcStartIso('01.08.2026') as string
    const dateTo = maskedDateToUtcEndIso('31.08.2026') as string

    // 02:00 Tashkent (+05:00) on 1 August 2026 is 21:00 UTC on 31 July 2026.
    const operationTimestamp = '2026-07-31T21:00:00.000Z'

    expect(operationTimestamp >= new Date(dateFrom).toISOString()).toBe(true)
    expect(operationTimestamp <= new Date(dateTo).toISOString()).toBe(true)
  })
})

describe('month → manual range round trip (Tashkent calendar day)', () => {
  it('pre-fills the first day of the month, not the previous day', () => {
    // `initializeRangeFromMonth` feeds `monthDateRange`'s `+05:00` strings straight
    // back into `isoDateToMaskedDate`. Reading the UTC calendar day off those returns
    // 31.07 for a range that starts on 01.08.
    const { rangeFrom, rangeTo } = initializeRangeFromMonth({ year: 2026, month: 8 })
    expect(rangeFrom).toBe('01.08.2026')
    expect(rangeTo).toBe('31.08.2026')
  })

  it('round trips every month boundary of the year', () => {
    for (let month = 1; month <= 12; month += 1) {
      const { rangeFrom } = initializeRangeFromMonth({ year: 2026, month })
      expect(rangeFrom.slice(0, 5)).toBe(`01.${String(month).padStart(2, '0')}`)
    }
  })

  it('reads the Tashkent day, not the UTC day, for an instant that straddles midnight', () => {
    // 2026-08-01T02:00 Tashkent is still 2026-07-31 in UTC.
    expect(isoDateToMaskedDate('2026-07-31T21:00:00.000Z')).toBe('01.08.2026')
  })
})
