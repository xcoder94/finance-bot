// dev-fix1 guard: the app never changes Telegram client colours (header/background/bottom bar).
import { beforeEach, describe, expect, it, vi } from 'vitest'

const m = vi.hoisted(() => ({ header: vi.fn(), bg: vi.fn(), bottom: vi.fn() }))
vi.mock('@tma.js/sdk-react', () => ({
  init: vi.fn(),
  on: vi.fn(),
  themeParams: { state: () => ({}) },
  miniApp: {
    setHeaderColor: Object.assign(m.header, { isAvailable: () => true }),
    setBgColor: Object.assign(m.bg, { isAvailable: () => true }),
    setBottomBarColor: Object.assign(m.bottom, { isAvailable: () => true }),
    mount: Object.assign(vi.fn(), { isAvailable: () => true }),
    isMounted: () => false,
    unmount: vi.fn(),
  },
}))

const cloud = vi.hoisted(() => ({ set: vi.fn() }))
vi.mock('./themeStorage', () => ({
  cloudGet: vi.fn(async () => 'light'),
  cloudSet: (k: string, v: string) => {
    cloud.set(k, v)
    return Promise.resolve()
  },
}))

beforeEach(() => {
  vi.resetModules()
  m.header.mockClear()
  m.bg.mockClear()
  m.bottom.mockClear()
  vi.stubGlobal('localStorage', { getItem: () => null, setItem: () => undefined })
  vi.stubGlobal('document', { documentElement: { dataset: {} as Record<string, string> } })
})

describe('Telegram client colours are left to Telegram', () => {
  it('theme change and hydrate never call setHeaderColor/setBgColor/setBottomBarColor', async () => {
    const { bindTelegramThemeParams } = await import('./bindThemeParams')
    bindTelegramThemeParams()
    const { useThemeStore } = await import('../store/themeStore')
    useThemeStore.getState().setTheme('light')
    useThemeStore.getState().setTheme('dark')
    await useThemeStore.getState().hydrate()
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(m.header).not.toHaveBeenCalled()
    expect(m.bg).not.toHaveBeenCalled()
    expect(m.bottom).not.toHaveBeenCalled()
  })
})
