import { beforeEach, describe, expect, it, vi } from 'vitest'

// Minimal hook runtime (no DOM available): slots per call order, effects run after render when deps changed.
const rt = vi.hoisted(() => ({
  slots: [] as unknown[],
  idx: 0,
  effects: [] as Array<() => void>,
  rerender: () => {},
}))
vi.mock('react', () => {
  const slot = <T,>(init: () => T): [number, T] => {
    const i = rt.idx++
    if (!(i in rt.slots)) rt.slots[i] = init()
    return [i, rt.slots[i] as T]
  }
  return {
    useState: (init: unknown) => {
      const [i, v] = slot(() => init)
      return [v, (n: unknown) => {
        rt.slots[i] = typeof n === 'function' ? (n as (p: unknown) => unknown)(rt.slots[i]) : n
        rt.rerender()
      }]
    },
    useReducer: (reducer: (s: unknown, a: unknown) => unknown, init: unknown) => {
      const [i, v] = slot(() => init)
      return [v, (a: unknown) => {
        const next = reducer(rt.slots[i], a)
        if (next !== rt.slots[i]) {
          rt.slots[i] = next
          rt.rerender()
        }
      }]
    },
    useEffect: (fn: () => void | (() => void), deps: unknown[]) => {
      const i = rt.idx++
      const prev = rt.slots[i] as { deps: unknown[]; cleanup?: void | (() => void) } | undefined
      if (prev && prev.deps.every((d, k) => Object.is(d, deps[k]))) return
      rt.effects.push(() => {
        if (prev?.cleanup) prev.cleanup()
        rt.slots[i] = { deps, cleanup: fn() }
      })
      rt.slots[i] = prev ?? { deps: [] }
      ;(rt.slots[i] as { deps: unknown[] }).deps = prev ? prev.deps : []
    },
  }
})
vi.mock('../api/admin', () => ({ fetchAdminUsage: vi.fn() }))

import { fetchAdminUsage } from '../api/admin'
import { useAdminOps } from './useAdminOps'

type Api = ReturnType<typeof useAdminOps>
let api: Api
let active = true
function render() {
  rt.idx = 0
  rt.effects = []
  api = useAdminOps(active)
  for (const run of rt.effects) run()
}
const flush = () => new Promise((r) => setTimeout(r, 0))
const fetchMock = vi.mocked(fetchAdminUsage)

beforeEach(() => {
  rt.slots = []
  rt.rerender = render
  active = true
  fetchMock.mockReset()
  fetchMock.mockResolvedValue({ period: 'day' } as never)
})

describe('useAdminOps', () => {
  it('requests once when the tab is active, nothing while inactive', async () => {
    active = false
    render()
    expect(fetchMock).not.toHaveBeenCalled()
    active = true
    render()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenLastCalledWith('day')
    await flush()
    expect(api.ops.status).toBe('ready')
  })
  it('a period change requests again for the new period', async () => {
    render()
    await flush()
    api.onPeriod('week')
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock).toHaveBeenLastCalledWith('week')
    await flush()
    expect(api.ops).toMatchObject({ period: 'week', status: 'ready' })
  })
  it('tapping the selected period neither sticks on loading nor re-requests', async () => {
    render()
    await flush()
    api.onPeriod('day')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(api.ops.status).toBe('ready')
  })
  it('"Повторить" after an error sends a new request and recovers', async () => {
    fetchMock.mockRejectedValueOnce(new Error('boom'))
    render()
    await flush()
    expect(api.ops.status).toBe('error')
    api.onRetry()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(api.ops.status).toBe('loading')
    await flush()
    expect(api.ops.status).toBe('ready')
  })
})
