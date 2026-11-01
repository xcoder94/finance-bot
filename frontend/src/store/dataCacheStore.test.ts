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
