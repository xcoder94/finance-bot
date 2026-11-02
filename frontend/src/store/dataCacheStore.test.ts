import { describe, expect, it } from 'vitest'

import {
  getCachedHomeSummary,
  getCachedTrend,
  invalidateHomeData,
  peekHomeSummary,
  peekTrend,
} from './dataCacheStore'
import type { SummaryResponse } from '../api/home'
import type { TrendEntry } from '../api/analytics'

const summary = { marker: 1 } as unknown as SummaryResponse
const trend: TrendEntry[] = [{ month: '2026-10', currency: 'UZS', expense: 5, income: 0 } as TrendEntry]

describe('home cache is stale-while-revalidate (dev-fix7)', () => {
  it('nothing is known before the first fetch', () => {
    expect(peekHomeSummary('fam-new', 2026, 10)).toBeNull()
    expect(peekTrend('fam-new', '2026-10')).toBeNull()
  })

  it('keeps showing the last value after invalidation, so the home never falls back to a skeleton', async () => {
    await getCachedHomeSummary('fam-a', 2026, 10, async () => summary)
    await getCachedTrend('fam-a', '2026-10', async () => trend)
    invalidateHomeData('fam-a')
    expect(peekHomeSummary('fam-a', 2026, 10)).toBe(summary)
    expect(peekTrend('fam-a', '2026-10')).toBe(trend)
  })

  it('after invalidation the next get refetches (data is stale, not fresh)', async () => {
    const fresh = { marker: 2 } as unknown as SummaryResponse
    await getCachedHomeSummary('fam-b', 2026, 10, async () => summary)
    invalidateHomeData('fam-b')
    expect(await getCachedHomeSummary('fam-b', 2026, 10, async () => fresh)).toBe(fresh)
    expect(peekHomeSummary('fam-b', 2026, 10)).toBe(fresh)
  })

  it('does not leak between families', async () => {
    await getCachedHomeSummary('fam-c', 2026, 10, async () => summary)
    expect(peekHomeSummary('fam-d', 2026, 10)).toBeNull()
  })
})

describe('homeEpoch (a mounted Home must refetch after a save)', () => {
  it('increments on every home invalidation', async () => {
    const { useDataCacheStore } = await import('./dataCacheStore')
    const before = useDataCacheStore.getState().homeEpoch
    invalidateHomeData('fam-e')
    expect(useDataCacheStore.getState().homeEpoch).toBe(before + 1)
  })
})

describe('any change refreshes every screen (dev-fix9)', () => {
  const cats = (n: number) => [{ id: 'c1', transaction_count: n }] as never
  const wallets = (name: string) => [{ id: 'w1', name }] as never

  it('editing a transaction invalidates categories and wallets, not only home', async () => {
    const { getCachedExpenseCategories, getCachedWallets, peekExpenseCategories, peekWallets, invalidateTransactionData } =
      await import('./dataCacheStore')
    await getCachedExpenseCategories('fam-f', async () => cats(1))
    await getCachedWallets('fam-f', async () => wallets('A'))
    invalidateTransactionData('fam-f', 't1')
    expect(peekExpenseCategories('fam-f')).toBeNull()
    expect(peekWallets('fam-f')).toBeNull()
  })

  it('renaming a wallet drops cached categories, transactions and home too', async () => {
    const { getCachedExpenseCategories, getCachedTransaction, peekTransaction, peekExpenseCategories, invalidateWalletData } =
      await import('./dataCacheStore')
    await getCachedExpenseCategories('fam-g', async () => cats(1))
    await getCachedTransaction('fam-g', 't1', async () => ({ id: 't1' }) as never)
    invalidateWalletData('fam-g')
    expect(peekExpenseCategories('fam-g')).toBeNull()
    expect(peekTransaction('fam-g', 't1')).toBeNull()
  })

  it('a category change drops wallets, home and transactions', async () => {
    const { getCachedWallets, peekWallets, invalidateExpenseCategoryData } = await import('./dataCacheStore')
    await getCachedWallets('fam-h', async () => wallets('A'))
    invalidateExpenseCategoryData('fam-h')
    expect(peekWallets('fam-h')).toBeNull()
  })

  it('a response that was requested before the change never lands in the cache', async () => {
    const { getCachedExpenseCategories, peekExpenseCategories, invalidateTransactionData } = await import('./dataCacheStore')
    let release: (v: never) => void = () => {}
    const slow = new Promise<never>((resolve) => { release = resolve })
    const old = getCachedExpenseCategories('fam-i', () => slow)
    invalidateTransactionData('fam-i', 't1')
    release(cats(1))
    await old
    expect(peekExpenseCategories('fam-i')).toBeNull()
    expect(await getCachedExpenseCategories('fam-i', async () => cats(0))).toEqual(cats(0))
  })
})
