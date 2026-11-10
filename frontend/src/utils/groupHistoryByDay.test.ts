import { describe, expect, it } from 'vitest'

import type { HistoryItem } from '../api/history'
import { dayHeaderKind, groupHistoryByDay } from './groupHistoryByDay'

function item(id: string, iso: string, type = 'expense', amount = 1000, currency = 'UZS'): HistoryItem {
  return { id, type, transaction_date: iso, amount, currency } as HistoryItem
}

describe('groupHistoryByDay', () => {
  it('groups by Tashkent day, keeps order, sums expenses per currency', () => {
    const groups = groupHistoryByDay([
      item('a', '2026-11-08T10:00:00+05:00', 'expense', 1000),
      item('b', '2026-11-08T08:00:00+05:00', 'expense', 500),
      item('c', '2026-11-08T07:00:00+05:00', 'income', 9000),
      item('d', '2026-11-07T23:30:00+05:00', 'expense', 200, 'USD'),
    ])
    expect(groups.map((g) => g.day)).toEqual(['2026-11-08', '2026-11-07'])
    expect(groups[0].items.map((i) => i.id)).toEqual(['a', 'b', 'c'])
    expect(groups[0].expenseTotals).toEqual([{ currency: 'UZS', amount: 1500 }])
    expect(groups[1].expenseTotals).toEqual([{ currency: 'USD', amount: 200 }])
  })

  it('day boundary uses Tashkent time, independent of the machine zone', () => {
    // 20:00 UTC on the 7th is already the 8th in Tashkent
    const groups = groupHistoryByDay([item('a', '2026-11-07T20:00:00Z')])
    expect(groups[0].day).toBe('2026-11-08')
  })

  it('a day without expenses has no total', () => {
    const groups = groupHistoryByDay([item('a', '2026-11-08T10:00:00+05:00', 'income')])
    expect(groups[0].expenseTotals).toEqual([])
  })
})

describe('dayHeaderKind', () => {
  it('today, yesterday, other', () => {
    expect(dayHeaderKind('2026-11-10', '2026-11-10')).toBe('today')
    expect(dayHeaderKind('2026-11-09', '2026-11-10')).toBe('yesterday')
    expect(dayHeaderKind('2026-11-08', '2026-11-10')).toBe('other')
  })
})
