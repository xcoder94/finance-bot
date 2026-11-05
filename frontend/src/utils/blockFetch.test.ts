import { describe, expect, it, vi } from 'vitest'

import { createBlockFetcher, type BlockState } from './blockFetch'

describe('createBlockFetcher', () => {
  const setup = (fetcher: () => Promise<number>) => {
    const states: BlockState<number>[] = []
    const block = createBlockFetcher({ fetcher, onChange: (s) => states.push(s) })
    return { block, states, last: () => states[states.length - 1] }
  }

  it('load: loading then success', async () => {
    const { block, states, last } = setup(vi.fn().mockResolvedValue(111))
    await block.load()
    expect(states[0]).toEqual({ status: 'loading' })
    expect(last()).toEqual({ status: 'success', data: 111 })
  })

  it('A: refresh replaces data without going through loading', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(111).mockResolvedValueOnce(333)
    const { block, states, last } = setup(fetcher)
    await block.load()
    const n = states.length
    const p = block.refresh()
    expect(states.length).toBe(n)
    await p
    expect(last()).toEqual({ status: 'success', data: 333 })
  })

  it('refresh failure keeps old data', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(111).mockRejectedValueOnce(new Error('x'))
    const { block, last } = setup(fetcher)
    await block.load()
    await block.refresh()
    expect(last()).toEqual({ status: 'success', data: 111 })
  })

  it('refresh failure during first load gives error, retry loads', async () => {
    let resolveFirst!: (v: number) => void
    const fetcher = vi
      .fn()
      .mockReturnValueOnce(new Promise<number>((r) => (resolveFirst = r)))
      .mockRejectedValueOnce(new Error('x'))
      .mockResolvedValueOnce(5)
    const { block, last } = setup(fetcher)
    const first = block.load()
    await block.refresh()
    resolveFirst(1)
    await first
    expect(last()).toEqual({ status: 'error' })
    await block.retry()
    expect(last()).toEqual({ status: 'success', data: 5 })
  })

  it('a stale answer after a newer load is ignored; dispose stops updates', async () => {
    let resolveOld!: (v: number) => void
    const fetcher = vi
      .fn()
      .mockReturnValueOnce(new Promise<number>((r) => (resolveOld = r)))
      .mockResolvedValueOnce(2)
    const { block, states, last } = setup(fetcher)
    const old = block.load()
    await block.load()
    resolveOld(1)
    await old
    expect(last()).toEqual({ status: 'success', data: 2 })
    block.dispose()
    const n = states.length
    await block.refresh()
    expect(states.length).toBe(n)
  })
})
