import type { HistoryItem } from '../api/history'
import { addDays, tashkentDateOf } from './dateChips'

export type DayGroup = {
  day: string
  items: HistoryItem[]
  expenseTotals: { currency: string; amount: number }[]
}

/** Groups an already sorted list by Tashkent calendar day; order of items is kept. */
export function groupHistoryByDay(items: HistoryItem[]): DayGroup[] {
  const groups: DayGroup[] = []
  const byDay = new Map<string, DayGroup>()
  for (const item of items) {
    const day = tashkentDateOf(item.transaction_date)
    let group = byDay.get(day)
    if (!group) {
      group = { day, items: [], expenseTotals: [] }
      byDay.set(day, group)
      groups.push(group)
    }
    group.items.push(item)
    if (item.type === 'expense') {
      const total = group.expenseTotals.find((row) => row.currency === item.currency)
      if (total) {
        total.amount += item.amount
      } else {
        group.expenseTotals.push({ currency: item.currency, amount: item.amount })
      }
    }
  }
  return groups
}

export function dayHeaderKind(day: string, today: string): 'today' | 'yesterday' | 'other' {
  if (day === today) {
    return 'today'
  }
  if (day === addDays(today, -1)) {
    return 'yesterday'
  }
  return 'other'
}
