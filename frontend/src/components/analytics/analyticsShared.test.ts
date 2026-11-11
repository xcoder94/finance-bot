import { describe, expect, it, vi } from 'vitest'

vi.mock('react', async () => {
  const { reactHarnessModule } = await import('../../test/hookHarness')
  return reactHarnessModule()
})

import { mountHook, useCallback } from '../../test/hookHarness'
import { useFetchBlock } from './analyticsShared'

function deferred<T>() {
  let resolve!: (v: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

describe('analytics useFetchBlock: quiet refresh on return (polish2 P3)', () => {
  it('epoch-only change keeps the old data on screen until the new data arrives', async () => {
    let epoch = 0
    let pending = deferred<string>()
    const fetcher = vi.fn(() => pending.promise)
    const h = await mountHook(() => {
      const f = useCallback(() => fetcher(), [])
      return useFetchBlock(f, `r|${epoch}`, true, false, 'r')
    })
    pending.resolve('old')
    await h.settle(10)
    expect(h.result().state).toEqual({ status: 'success', data: 'old' })

    epoch = 1
    pending = deferred<string>()
    h.rerender()
    await h.settle(5)
    expect(h.result().state).toEqual({ status: 'success', data: 'old' })
    pending.resolve('new')
    await h.settle(10)
    expect(h.result().state).toEqual({ status: 'success', data: 'new' })
    expect(fetcher).toHaveBeenCalledTimes(2)
  })

  it('a period change (reset key) shows loading again, not the previous period', async () => {
    let reset = 'month-1'
    let pending = deferred<string>()
    const h = await mountHook(() => {
      const f = useCallback(() => pending.promise, [])
      return useFetchBlock(f, `${reset}|0`, true, false, reset)
    })
    pending.resolve('a')
    await h.settle(10)
    reset = 'month-2'
    pending = deferred<string>()
    h.rerender()
    await h.settle(5)
    expect(h.result().state).toEqual({ status: 'loading' })
  })

  it('a failed quiet refresh keeps the old data instead of an error block', async () => {
    let epoch = 0
    let next: Promise<string> = Promise.resolve('old')
    const h = await mountHook(() => {
      const f = useCallback(() => next, [])
      return useFetchBlock(f, `r|${epoch}`, true, false, 'r')
    })
    await h.settle(10)
    epoch = 1
    next = Promise.reject(new Error('net'))
    h.rerender()
    await h.settle(10)
    expect(h.result().state).toEqual({ status: 'success', data: 'old' })
  })
})
