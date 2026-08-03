import type { HistoryItem } from '../api/home'

export function editRouteForItem(item: Pick<HistoryItem, 'id' | 'type'>): string {
  if (item.type === 'income') {
    return `/edit-income/${item.id}`
  }
  if (item.type === 'expense') {
    return `/edit-expense/${item.id}`
  }
  return `/edit-transfer/${item.id}`
}
