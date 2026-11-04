import type { HistoryItem, HistoryResponse } from '../api/history'
import { formatHistoryTransactionAmount } from '../components/history/historyTransactionDisplay'
import { formatCurrency, type Currency } from './formatCurrency'

export const WALLET_OPS_PAGE_SIZE = 50
const MAX_PAGE = 500

export const WALLETS_LIST_PATH = '/wallets'

export function walletOpsPath(walletId: string): string {
  return `${WALLETS_LIST_PATH}/${walletId}`
}

/** Amount as seen from one wallet: a transfer out is minus, a transfer in is plus (to_amount). */
export function walletOpAmount(item: HistoryItem, walletId: string): string {
  if (item.type === 'transfer') {
    if (item.wallet_id === walletId) {
      return `−${formatCurrency(item.amount, item.currency as Currency)}`
    }
    if (item.to_wallet_id === walletId) {
      return `+${formatCurrency(item.to_amount ?? item.amount, (item.to_currency ?? item.currency) as Currency)}`
    }
  }
  return formatHistoryTransactionAmount(item)
}

export function mergeUniqueById<T extends { id: string }>(current: T[], more: T[]): T[] {
  const seen = new Set(current.map((entry) => entry.id))
  return [...current, ...more.filter((entry) => !seen.has(entry.id))]
}

export type WalletScreen<W> = { kind: 'loading' } | { kind: 'missing' } | { kind: 'ready'; wallet: W }

/** "Missing" only on a list that was just fetched: a cached list may lack a brand-new wallet. */
export function resolveWalletScreen<W extends { id: string }>(
  wallets: W[] | null,
  fresh: boolean,
  walletId: string,
): WalletScreen<W> {
  const wallet = wallets?.find((entry) => entry.id === walletId)
  if (wallet) return { kind: 'ready', wallet }
  return wallets && fresh ? { kind: 'missing' } : { kind: 'loading' }
}

export function leaveIfWalletMissing(
  screen: WalletScreen<unknown>,
  navigate: (to: string, options: { replace: boolean }) => void,
): void {
  if (screen.kind === 'missing') navigate(WALLETS_LIST_PATH, { replace: true })
}

export type WalletOpsRange = { dateFrom: string; dateTo: string }

export type WalletOpsState = {
  status: 'loading' | 'error' | 'success'
  items: HistoryItem[]
  total: number
  loadingMore: boolean
  loadMoreError: boolean
}

export type WalletOpsController = {
  setPeriod: (range: WalletOpsRange) => Promise<void>
  retry: () => Promise<void>
  refresh: () => Promise<void>
  loadMore: () => Promise<void>
  dispose: () => void
}

type ControllerDeps = {
  fetchPage: (range: WalletOpsRange, limit: number, offset: number) => Promise<HistoryResponse>
  onChange: (state: WalletOpsState) => void
}

/** Framework-free list state of one wallet screen: period switch, refresh, paging, stale answers. */
export function createWalletOpsController({ fetchPage, onChange }: ControllerDeps): WalletOpsController {
  let state: WalletOpsState = { status: 'loading', items: [], total: 0, loadingMore: false, loadMoreError: false }
  let period: WalletOpsRange | null = null
  let seq = 0
  let disposed = false

  const emit = (next: WalletOpsState) => {
    state = next
    if (!disposed) onChange(state)
  }

  const load = async (range: WalletOpsRange) => {
    const mine = ++seq
    emit({ status: 'loading', items: [], total: 0, loadingMore: false, loadMoreError: false })
    try {
      const data = await fetchPage(range, WALLET_OPS_PAGE_SIZE, 0)
      if (mine !== seq) return
      emit({ status: 'success', items: data.items, total: data.total_count, loadingMore: false, loadMoreError: false })
    } catch {
      if (mine !== seq) return
      emit({ status: 'error', items: [], total: 0, loadingMore: false, loadMoreError: false })
    }
  }

  return {
    setPeriod(range) {
      period = range
      return load(range)
    },
    retry() {
      return period ? load(period) : Promise.resolve()
    },
    async refresh() {
      if (!period) return
      const range = period
      const mine = ++seq
      const limit = Math.min(MAX_PAGE, Math.max(WALLET_OPS_PAGE_SIZE, state.items.length))
      try {
        const data = await fetchPage(range, limit, 0)
        if (mine !== seq) return
        emit({ status: 'success', items: data.items, total: data.total_count, loadingMore: false, loadMoreError: false })
      } catch {
        if (mine !== seq) return
        // keep what is on screen; a failed background refresh must not wipe the list
        if (state.loadingMore) emit({ ...state, loadingMore: false })
      }
    },
    async loadMore() {
      if (!period || state.status !== 'success' || state.loadingMore || state.items.length >= state.total) return
      const mine = seq
      emit({ ...state, loadingMore: true, loadMoreError: false })
      try {
        const data = await fetchPage(period, WALLET_OPS_PAGE_SIZE, state.items.length)
        if (mine !== seq) return
        emit({
          ...state,
          items: mergeUniqueById(state.items, data.items),
          total: data.total_count,
          loadingMore: false,
        })
      } catch {
        if (mine !== seq) return
        emit({ ...state, loadingMore: false, loadMoreError: true })
      }
    },
    dispose() {
      disposed = true
    },
  }
}
