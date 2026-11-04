import { getWallets } from '../api/wallets'
import type { Wallet } from '../api/transactions'
import { getCachedWallets } from '../store/dataCacheStore'
import { shouldRefreshHomeOnVisibility } from './homeVisibility'

export type WalletsOverviewItem = Pick<
  Wallet,
  'id' | 'name' | 'translation_key' | 'currency' | 'is_personal' | 'balance'
>

const CURRENCY_ORDER = ['UZS', 'USD']

export function groupWallets<T extends WalletsOverviewItem>(
  wallets: T[],
): { shared: T[]; personal: T[] } {
  return {
    shared: wallets.filter((wallet) => !wallet.is_personal),
    personal: wallets.filter((wallet) => wallet.is_personal),
  }
}

/** Sum of every shown wallet (personal included), one entry per currency. */
export function totalsByCurrency(
  wallets: WalletsOverviewItem[],
): Array<{ currency: string; total: number }> {
  const sums = new Map<string, number>()
  for (const wallet of wallets) {
    sums.set(wallet.currency, (sums.get(wallet.currency) ?? 0) + wallet.balance)
  }
  const rank = (currency: string) => {
    const i = CURRENCY_ORDER.indexOf(currency)
    return i === -1 ? CURRENCY_ORDER.length : i
  }
  return [...sums.entries()]
    .sort((a, b) => rank(a[0]) - rank(b[0]) || a[0].localeCompare(b[0]))
    .map(([currency, total]) => ({ currency, total }))
}

/** A bot write does not clear the client cache: always ask the server, skipping the cache. */
export function loadFreshWallets(
  familyId: string,
  fetcher: () => Promise<Wallet[]> = getWallets,
): Promise<Wallet[]> {
  return getCachedWallets(familyId, fetcher, true)
}

type VisibilityDoc = {
  visibilityState: DocumentVisibilityState
  addEventListener: (type: 'visibilitychange', handler: () => void) => void
  removeEventListener: (type: 'visibilitychange', handler: () => void) => void
}

export function subscribeWalletsRefresh(doc: VisibilityDoc, onRefresh: () => void): () => void {
  const handler = () => {
    if (shouldRefreshHomeOnVisibility(doc.visibilityState)) onRefresh()
  }
  doc.addEventListener('visibilitychange', handler)
  return () => doc.removeEventListener('visibilitychange', handler)
}
