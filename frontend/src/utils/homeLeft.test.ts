import { describe, expect, it } from 'vitest'

import { daysLeftInMonth, perDayAllowance, remainingFromSummary } from './homeLeft'

const oct = { year: 2026, month: 10 }

describe('daysLeftInMonth (Tashkent, today included)', () => {
  it('first day of the month counts the whole month', () => {
    expect(daysLeftInMonth(new Date('2026-10-01T10:00:00+05:00'), oct)).toBe(31)
  })

  it('last day of the month is 1', () => {
    expect(daysLeftInMonth(new Date('2026-10-31T10:00:00+05:00'), oct)).toBe(1)
  })

  it('mid month (mockup: 14 days)', () => {
    expect(daysLeftInMonth(new Date('2026-10-18T12:00:00+05:00'), oct)).toBe(14)
  })

  it('day rolls over at Tashkent midnight, not UTC midnight', () => {
    // 23:59 Tashkent on the 30th is still 19:00Z of the 30th
    expect(daysLeftInMonth(new Date('2026-10-30T18:59:00Z'), oct)).toBe(2)
    // 00:00 Tashkent on the 31st = 19:00Z of the 30th
    expect(daysLeftInMonth(new Date('2026-10-30T19:00:00Z'), oct)).toBe(1)
  })

  it('month rollover by Tashkent clock: 31 Oct 19:00Z is already 1 Nov', () => {
    expect(daysLeftInMonth(new Date('2026-10-31T19:00:00Z'), oct)).toBeNull()
    expect(daysLeftInMonth(new Date('2026-10-31T19:00:00Z'), { year: 2026, month: 11 })).toBe(30)
  })

  it('leap February', () => {
    expect(daysLeftInMonth(new Date('2028-02-28T10:00:00+05:00'), { year: 2028, month: 2 })).toBe(2)
    expect(daysLeftInMonth(new Date('2027-02-28T10:00:00+05:00'), { year: 2027, month: 2 })).toBe(1)
  })

  it('past month has no daily allowance', () => {
    expect(daysLeftInMonth(new Date('2026-10-18T12:00:00+05:00'), { year: 2026, month: 9 })).toBeNull()
    expect(daysLeftInMonth(new Date('2026-01-05T12:00:00+05:00'), { year: 2025, month: 12 })).toBeNull()
  })

  it('future month counts all of its days', () => {
    expect(daysLeftInMonth(new Date('2026-10-18T12:00:00+05:00'), { year: 2026, month: 12 })).toBe(31)
  })
})

describe('perDayAllowance', () => {
  it('rounds down to 100 so\'m (mockup 3 450 000 / 14 -> 246 400)', () => {
    expect(perDayAllowance(3_450_000, 14)).toBe(246_400)
  })

  it('past month -> null', () => {
    expect(perDayAllowance(3_450_000, null)).toBeNull()
  })

  it('negative remainder stays negative, magnitude rounded down', () => {
    expect(perDayAllowance(-1_000_000, 3)).toBe(-333_300)
  })

  it('zero', () => {
    expect(perDayAllowance(0, 5)).toBe(0)
  })

  it('below 100 gives 0 (never -0)', () => {
    expect(Object.is(perDayAllowance(-50, 1), 0)).toBe(true)
    expect(perDayAllowance(99, 1)).toBe(0)
  })
})

describe('remainingFromSummary', () => {
  it('income - expense of UZS, ignoring net_change (transfers)', () => {
    const summary = {
      by_currency: [
        { currency: 'UZS', income: 500, expense: 120, net_change: 9999 },
      ],
    }
    expect(remainingFromSummary(summary as never)).toBe(380)
  })

  it('no UZS row -> 0', () => {
    expect(remainingFromSummary({ by_currency: [] } as never)).toBe(0)
  })
})

import { monthHasIncome } from './homeLeft'

describe('monthHasIncome (no income -> no daily allowance)', () => {
  const sum = (rows: Array<{ currency: string; income: number; expense: number }>) =>
    ({ by_currency: rows } as never)
  it('true only when the UZS row has income > 0', () => {
    expect(monthHasIncome(sum([{ currency: 'UZS', income: 5000000, expense: 100 }]))).toBe(true)
    expect(monthHasIncome(sum([{ currency: 'UZS', income: 0, expense: 100 }]))).toBe(false)
    expect(monthHasIncome(sum([]))).toBe(false)
    expect(monthHasIncome(sum([{ currency: 'USD', income: 10, expense: 0 }]))).toBe(false)
  })
})
