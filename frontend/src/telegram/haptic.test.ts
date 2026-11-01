import { afterEach, describe, expect, it } from 'vitest'

import { haptic, isHapticTapTarget, resetHapticDriver, setHapticDriver } from './haptic'

type Call = [string, string]

function recordingDriver(calls: Call[]) {
  return {
    impact: (style: string) => calls.push(['impact', style]),
    notification: (type: string) => calls.push(['notification', type]),
  }
}

afterEach(() => resetHapticDriver())

describe('haptic', () => {
  it('maps light/success/error to Telegram feedback kinds', () => {
    const calls: Call[] = []
    setHapticDriver(recordingDriver(calls))
    haptic.light()
    haptic.success()
    haptic.error()
    expect(calls).toEqual([
      ['impact', 'light'],
      ['notification', 'success'],
      ['notification', 'error'],
    ])
  })

  it('never throws when the client has no haptics', () => {
    setHapticDriver({
      impact: () => {
        throw new Error('unsupported')
      },
      notification: () => {
        throw new Error('unsupported')
      },
    })
    expect(() => {
      haptic.light()
      haptic.success()
      haptic.error()
    }).not.toThrow()
  })

  it('does not throw outside Telegram with the default driver', () => {
    expect(() => haptic.light()).not.toThrow()
  })
})

describe('isHapticTapTarget', () => {
  const el = (match: string | null, disabled = false) => ({
    closest: () =>
      match === null
        ? null
        : { disabled, getAttribute: (n: string) => (n === 'aria-disabled' && disabled ? 'true' : null) },
  })

  it('accepts buttons and tab links, rejects the rest', () => {
    expect(isHapticTapTarget(el('button'))).toBe(true)
    expect(isHapticTapTarget(el(null))).toBe(false)
    expect(isHapticTapTarget(null)).toBe(false)
  })

  it('rejects disabled buttons', () => {
    expect(isHapticTapTarget(el('button', true))).toBe(false)
  })
})
