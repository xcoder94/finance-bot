import { describe, expect, it, vi } from 'vitest'

import { subscribeBridgeVisible } from './bridgeVisibility'

describe('subscribeBridgeVisible', () => {
  it('calls back only when the bridge says the app became visible, and unsubscribes', () => {
    let handler: ((p: { is_visible?: boolean }) => void) | undefined
    const off = vi.fn()
    const on = vi.fn((_name: string, cb: (p: { is_visible?: boolean }) => void) => {
      handler = cb
      return off
    })
    const cb = vi.fn()
    const stop = subscribeBridgeVisible(cb, on as never)
    expect(on).toHaveBeenCalledWith('visibility_changed', expect.any(Function))
    handler!({ is_visible: false })
    expect(cb).not.toHaveBeenCalled()
    handler!({ is_visible: true })
    expect(cb).toHaveBeenCalledTimes(1)
    stop()
    expect(off).toHaveBeenCalled()
  })

  it('no bridge: no throw, no-op unsubscribe', () => {
    const on = () => {
      throw new Error('no bridge')
    }
    const stop = subscribeBridgeVisible(() => {}, on as never)
    expect(() => stop()).not.toThrow()
  })
})
