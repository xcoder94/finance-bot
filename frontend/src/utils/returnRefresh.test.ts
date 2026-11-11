import { afterEach, describe, expect, it, vi } from 'vitest'

import { useDataCacheStore, invalidateFamilyData } from '../store/dataCacheStore'
import { createReturnRefresher, RETURN_REFRESH_THROTTLE_MS } from './returnRefresh'

function setup(startAt = 1_000_000) {
  let now = startAt
  const refresh = vi.fn()
  const r = createReturnRefresher({ now: () => now, onRefresh: refresh })
  return { r, refresh, advance: (ms: number) => (now += ms) }
}

afterEach(() => vi.useRealTimers())

describe('refresh on return to the app', () => {
  it('one request set per return, even when visibilitychange, activated and the bridge all fire', () => {
    const { r, refresh, advance } = setup()
    advance(RETURN_REFRESH_THROTTLE_MS + 1)
    r.onReturn()
    r.onReturn()
    r.onReturn()
    expect(refresh).toHaveBeenCalledTimes(1)
  })

  it('nothing at all while idle: no timers, no polling', () => {
    vi.useFakeTimers()
    const { refresh } = setup()
    vi.advanceTimersByTime(10 * 60_000)
    expect(refresh).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('quick app switching is throttled to one refresh per 30 s', () => {
    const { r, refresh, advance } = setup()
    advance(RETURN_REFRESH_THROTTLE_MS)
    r.onReturn() // 1
    for (let i = 0; i < 10; i += 1) {
      advance(2_000)
      r.onReturn()
    }
    expect(refresh).toHaveBeenCalledTimes(1)
    advance(RETURN_REFRESH_THROTTLE_MS)
    r.onReturn() // 2
    expect(refresh).toHaveBeenCalledTimes(2)
  })

  it('a return right after the app opened does not refetch what was just loaded', () => {
    const { r, refresh, advance } = setup()
    advance(5_000)
    r.onReturn()
    expect(refresh).not.toHaveBeenCalled()
  })
})

describe('the refresh is one invalidation = one epoch bump', () => {
  it('bumps homeEpoch exactly once per accepted return', () => {
    const before = useDataCacheStore.getState().homeEpoch
    let now = 0
    const r = createReturnRefresher({ now: () => now, onRefresh: () => invalidateFamilyData('f1') })
    now += RETURN_REFRESH_THROTTLE_MS
    r.onReturn()
    r.onReturn()
    expect(useDataCacheStore.getState().homeEpoch).toBe(before + 1)
  })
})
