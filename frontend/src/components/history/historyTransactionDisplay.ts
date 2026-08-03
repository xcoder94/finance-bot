import type { HistoryItem } from '../../api/history'
import { formatCurrency, type Currency } from '../../utils/formatCurrency'

export function formatTransactionDateShort(isoDate: string): string {
  return new Intl.DateTimeFormat('ru-RU', {
    timeZone: 'Asia/Tashkent',
    day: '2-digit',
    month: '2-digit',
  }).format(new Date(isoDate))
}

function isTransferLike(item: HistoryItem): boolean {
  return item.type === 'transfer'
}

export function formatHistoryTransactionAmount(item: HistoryItem): string {
  const formatted = formatCurrency(item.amount, item.currency as Currency)
  if (isTransferLike(item)) {
    return `↔\u2009${formatted}`
  }
  if (item.type === 'income') {
    return `+${formatted}`
  }
  if (item.type === 'expense') {
    return `−${formatted}`
  }
  return formatted
}

export function historyAmountClass(item: HistoryItem): string {
  if (isTransferLike(item)) {
    return 'home-ops-row__amount home-ops-row__amount--neutral'
  }
  if (item.type === 'expense') {
    return 'home-ops-row__amount home-ops-row__amount--expense'
  }
  if (item.type === 'income') {
    return 'home-ops-row__amount home-ops-row__amount--income'
  }
  return 'home-ops-row__amount'
}
