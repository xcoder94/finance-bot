// QA m3-1: Telegram header/background follow the chosen in-app theme.
import { beforeEach, describe, expect, it, vi } from 'vitest'

const m = vi.hoisted(() => ({ header: vi.fn(), bg: vi.fn(), available: true }))
vi.mock('@tma.js/sdk-react', () => ({
  miniApp: {
    setHeaderColor: Object.assign(m.header, { isAvailable: () => m.available }),
    setBgColor: Object.assign(m.bg, { isAvailable: () => m.available }),
  },
}))

import { applyTelegramChrome } from './telegramChrome'

beforeEach(() => {
  m.header.mockClear()
  m.bg.mockClear()
  m.available = true
})

describe('applyTelegramChrome', () => {
  it('dark -> #17212b (matches --bg of dark palette)', () => {
    applyTelegramChrome('dark')
    expect(m.header).toHaveBeenCalledWith('#17212b')
    expect(m.bg).toHaveBeenCalledWith('#17212b')
  })
  it('light -> #ffffff', () => {
    applyTelegramChrome('light')
    expect(m.header).toHaveBeenCalledWith('#ffffff')
    expect(m.bg).toHaveBeenCalledWith('#ffffff')
  })
  it('old Telegram client without the methods: silently skipped', () => {
    m.available = false
    expect(() => applyTelegramChrome('light')).not.toThrow()
    expect(m.header).not.toHaveBeenCalled()
  })
})
