// dev-fix11: System mode follows Telegram live (themeChanged, return from background), choice persists.
import { beforeEach, describe, expect, it, vi } from 'vitest'

const tg = vi.hoisted(() => ({
  scheme: 'dark' as 'dark' | 'light' | null,
  listener: null as null | (() => void),
}))

vi.mock('../telegram/colorScheme', () => ({
  readTelegramScheme: () => tg.scheme,
  readMediaScheme: () => null,
  watchSystemScheme: (cb: () => void) => {
    tg.listener = cb
    return () => {
      tg.listener = null
    }
  },
}))
vi.mock('../telegram/themeStorage', () => ({
  cloudGet: vi.fn(async () => null),
  cloudSet: vi.fn(async () => undefined),
}))

const local = new Map<string, string>()

async function freshStore() {
  vi.resetModules()
  return import('./themeStore')
}

beforeEach(() => {
  local.clear()
  tg.scheme = 'dark'
  tg.listener = null
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => local.get(k) ?? null,
    setItem: (k: string, v: string) => void local.set(k, v),
  })
  vi.stubGlobal('document', { documentElement: { dataset: {} as Record<string, string> } })
})

describe('theme preference', () => {
  it('first launch is System and follows Telegram (dark and light)', async () => {
    const dark = await freshStore()
    expect(dark.useThemeStore.getState().preference).toBe('system')
    expect(dark.useThemeStore.getState().theme).toBe('dark')
    tg.scheme = 'light'
    const light = await freshStore()
    expect(light.useThemeStore.getState().theme).toBe('light')
  })

  it('a value saved before dev-fix11 (explicit light/dark) is kept as a manual choice', async () => {
    local.set('app-theme', 'light')
    tg.scheme = 'dark'
    const { useThemeStore } = await freshStore()
    expect(useThemeStore.getState().preference).toBe('light')
    expect(useThemeStore.getState().theme).toBe('light')
  })

  it('switches live when Telegram changes theme, and applies it to the document', async () => {
    const { useThemeStore } = await freshStore()
    const stop = useThemeStore.getState().watchSystem()
    expect(document.documentElement.dataset.theme).toBe('dark')
    tg.scheme = 'light'
    tg.listener?.() // themeChanged
    expect(useThemeStore.getState().theme).toBe('light')
    expect(document.documentElement.dataset.theme).toBe('light')
    stop()
    expect(tg.listener).toBeNull()
  })

  it('re-reads the scheme on return from background (listener fires, state was stale)', async () => {
    const { useThemeStore } = await freshStore()
    useThemeStore.getState().watchSystem()
    tg.scheme = 'light' // phone switched on schedule while the app was in background
    tg.listener?.() // visibilitychange / activated / focus
    expect(useThemeStore.getState().theme).toBe('light')
    tg.scheme = 'dark'
    tg.listener?.()
    expect(useThemeStore.getState().theme).toBe('dark')
  })

  it('manual Light/Dark ignores Telegram changes; going back to System follows again', async () => {
    const { useThemeStore } = await freshStore()
    useThemeStore.getState().watchSystem()
    useThemeStore.getState().setPreference('light')
    tg.scheme = 'dark'
    tg.listener?.()
    expect(useThemeStore.getState().theme).toBe('light')
    useThemeStore.getState().setPreference('system')
    expect(useThemeStore.getState().theme).toBe('dark')
    expect(local.get('app-theme')).toBe('system')
  })

  it('persists every mode across restart', async () => {
    for (const mode of ['system', 'light', 'dark'] as const) {
      const first = await freshStore()
      first.useThemeStore.getState().setPreference(mode)
      const second = await freshStore()
      expect(second.useThemeStore.getState().preference).toBe(mode)
    }
  })
})
