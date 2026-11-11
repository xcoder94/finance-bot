import { describe, expect, it, vi } from 'vitest'

vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../test/hookHarness')
  return reactHarnessModule()
})

import { mountHook, useCallback } from '../test/hookHarness'
import { useFetchBlock } from './useFetchBlock'

describe('Home useFetchBlock: no request loop (N1)', () => {
  it('forced fetch whose result changes the cache reference does not refetch endlessly', async () => {
    let cache: string[] | null = null // peekWallets(): new array after every fetch
    const fetcher = vi.fn(async () => {
      cache = ['w1']
      return cache
    })
    const h = await mountHook(() => {
      const f = useCallback(() => fetcher(), [])
      return useFetchBlock(f, 'trigger', cache ? [...cache] : null)
    })
    await h.settle(100)
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(h.result().state).toEqual({ status: 'success', data: ['w1'] })
  })

  it('plain re-renders and a fresh cache copy every render never refetch', async () => {
    const fetcher = vi.fn(async () => ['a'])
    const h = await mountHook(() => {
      const f = useCallback(() => fetcher(), [])
      return useFetchBlock(f, 'x', ['cached'])
    })
    for (let i = 0; i < 20; i += 1) h.rerender()
    await h.settle(20)
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('refetches when the trigger or the key changes (month switch, invalidation)', async () => {
    const fetcher = vi.fn(async () => ['a'])
    let trigger = 1
    let key = 'm1'
    const h = await mountHook(() => {
      const f = useCallback(() => fetcher(), [])
      return useFetchBlock(f, trigger, null, key)
    })
    expect(fetcher).toHaveBeenCalledTimes(1)
    trigger = 2
    h.rerender()
    await h.settle(10)
    expect(fetcher).toHaveBeenCalledTimes(2)
    key = 'm2'
    h.rerender()
    await h.settle(10)
    expect(fetcher).toHaveBeenCalledTimes(3)
  })
})
