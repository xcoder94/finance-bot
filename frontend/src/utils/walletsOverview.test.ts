import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDataCacheStore, getCachedWallets } from '../store/dataCacheStore'
import {
  groupWallets,
  loadFreshWallets,
  subscribeWalletsRefresh,
  totalsByCurrency,
  type WalletsOverviewItem,
} from './walletsOverview'
import { peekHomeMonth, rememberHomeMonth, forgetHomeMonth } from './homeMonthMemory'

const w = (
  id: string,
  balance: number,
  over: Partial<WalletsOverviewItem> = {},
): WalletsOverviewItem => ({
  id,
  name: id,
  translation_key: null,
  currency: 'UZS',
  is_personal: false,
  balance,
  ...over,
})

describe('groupWallets / totalsByCurrency', () => {
  const list = [w('a', 1000), w('b', -300), w('p', 500, { is_personal: true })]

  it('splits shared and personal', () => {
    const g = groupWallets(list)
    expect(g.shared.map((x) => x.id)).toEqual(['a', 'b'])
    expect(g.personal.map((x) => x.id)).toEqual(['p'])
  })

  it('total includes personal wallets', () => {
    expect(totalsByCurrency(list)).toEqual([{ currency: 'UZS', total: 1200 }])
  })

  it('currencies are never summed together, each keeps its own sign', () => {
    const t = totalsByCurrency([
      w('a', 1000),
      w('u', -50, { currency: 'USD' }),
      w('u2', -20, { currency: 'USD' }),
    ])
    expect(t).toEqual([
      { currency: 'UZS', total: 1000 },
      { currency: 'USD', total: -70 },
    ])
  })

  it('no wallets: no totals, no groups', () => {
    expect(totalsByCurrency([])).toEqual([])
    expect(groupWallets([])).toEqual({ shared: [], personal: [] })
  })
})

describe('fresh data', () => {
  beforeEach(() => useDataCacheStore.setState({ entries: {} }))

  it('loadFreshWallets bypasses a fresh cache entry', async () => {
    await getCachedWallets('fam', async () => [w('old', 1) as never])
    const fetcher = vi.fn(async () => [w('new', 2) as never])
    const result = await loadFreshWallets('fam', fetcher)
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(result.map((x) => x.id)).toEqual(['new'])
  })

  it('refetches on visibilitychange to visible, not when hidden, and unsubscribes', () => {
    const handlers: Array<() => void> = []
    const doc = {
      visibilityState: 'hidden' as DocumentVisibilityState,
      addEventListener: (_: string, h: () => void) => handlers.push(h),
      removeEventListener: (_: string, h: () => void) => {
        handlers.splice(handlers.indexOf(h), 1)
      },
    }
    const cb = vi.fn()
    const off = subscribeWalletsRefresh(doc, cb)
    handlers.forEach((h) => h())
    expect(cb).not.toHaveBeenCalled()
    doc.visibilityState = 'visible'
    handlers.forEach((h) => h())
    expect(cb).toHaveBeenCalledTimes(1)
    off()
    expect(handlers).toHaveLength(0)
  })
})

describe('home month memory', () => {
  it('keeps the month until forgotten', () => {
    forgetHomeMonth()
    expect(peekHomeMonth()).toBeNull()
    rememberHomeMonth({ year: 2026, month: 8 })
    expect(peekHomeMonth()).toEqual({ year: 2026, month: 8 })
    forgetHomeMonth()
    expect(peekHomeMonth()).toBeNull()
  })
})

import { openWalletsFromHome, WALLETS_PATH } from './homeMonthMemory'

describe('openWalletsFromHome', () => {
  it('navigates to /wallets and keeps the month for the way back', () => {
    forgetHomeMonth()
    const navigate = vi.fn()
    openWalletsFromHome({ year: 2026, month: 3 }, navigate)
    expect(navigate).toHaveBeenCalledWith(WALLETS_PATH)
    expect(WALLETS_PATH).toBe('/wallets')
    expect(peekHomeMonth()).toEqual({ year: 2026, month: 3 })
    forgetHomeMonth()
  })
})
