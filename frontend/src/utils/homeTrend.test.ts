import { describe, expect, it } from 'vitest'

import { buildTrend3, formatMillions, trendMonthLabel } from './homeTrend'

describe('buildTrend3', () => {
  const entries = [
    { month: '2026-06', currency: 'UZS', income: 1, expense: 7_900_000 },
    { month: '2026-07', currency: 'UZS', income: 1, expense: 9_100_000 },
    { month: '2026-08', currency: 'UZS', income: 1, expense: 8_950_000 },
    { month: '2026-08', currency: 'USD', income: 1, expense: 5 },
    { month: '2026-05', currency: 'UZS', income: 1, expense: 1 },
  ]

  it('takes 3 months ending at the selected one, UZS only', () => {
    const bars = buildTrend3(entries, { year: 2026, month: 8 })
    expect(bars.map((b) => b.month)).toEqual([6, 7, 8])
    expect(bars.map((b) => b.expense)).toEqual([7_900_000, 9_100_000, 8_950_000])
  })

  it('crosses the year boundary', () => {
    const bars = buildTrend3([], { year: 2026, month: 1 })
    expect(bars.map((b) => [b.year, b.month])).toEqual([[2025, 11], [2025, 12], [2026, 1]])
  })

  it('missing months and empty list become zeros; last bar is the selected month', () => {
    const bars = buildTrend3([], { year: 2026, month: 8 })
    expect(bars.map((b) => b.expense)).toEqual([0, 0, 0])
    expect(bars.map((b) => b.current)).toEqual([false, false, true])
  })

  it('bar height scales to the max, minimum 2px for zero', () => {
    const bars = buildTrend3(entries, { year: 2026, month: 8 })
    expect(bars[1].heightPx).toBe(40)
    expect(bars[0].heightPx).toBeCloseTo(40 * 7.9 / 9.1, 5)
    const empty = buildTrend3([], { year: 2026, month: 8 })
    expect(empty.map((b) => b.heightPx)).toEqual([2, 2, 2])
  })
})

describe('formatMillions', () => {
  it('up to two decimals with comma like the mockup, trailing zeros dropped (B4)', () => {
    expect(formatMillions(7_900_000)).toBe('7,9')
    expect(formatMillions(9_000_000)).toBe('9')
    expect(formatMillions(8_950_000)).toBe('8,95')
    expect(formatMillions(9_100_000)).toBe('9,1')
    expect(formatMillions(0)).toBe('0')
    expect(formatMillions(120_000)).toBe('0,12')
    expect(formatMillions(8_954_000)).toBe('8,95')
  })
})

describe('trendMonthLabel', () => {
  it('uniform 3-letter capitalised labels (mockup: Июн Июл Авг)', () => {
    expect([6, 7, 8, 3, 9, 5].map(trendMonthLabel)).toEqual(['Июн', 'Июл', 'Авг', 'Мар', 'Сен', 'Май'])
    expect(trendMonthLabel(1)).toBe('Янв')
    expect(trendMonthLabel(12)).toBe('Дек')
  })
})
