import { afterEach, describe, expect, it } from 'vitest'

import { resetHapticDriver, setHapticDriver } from '../telegram/haptic'
import { celebrateSave, useSuccessFlashStore } from './successFlashStore'

afterEach(() => resetHapticDriver())

describe('celebrateSave', () => {
  it('fires success haptic and bumps the flash token', () => {
    const calls: string[] = []
    setHapticDriver({ impact: () => undefined, notification: (t) => calls.push(t) })
    const before = useSuccessFlashStore.getState().token
    celebrateSave()
    expect(calls).toEqual(['success'])
    expect(useSuccessFlashStore.getState().token).toBe(before + 1)
  })
})
