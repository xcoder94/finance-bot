import { beforeEach, describe, expect, it, vi } from 'vitest'

const cloud = vi.hoisted(() => ({ value: null as string | null, set: vi.fn() }))
const chrome = vi.hoisted(() => ({ apply: vi.fn() }))

vi.mock('../telegram/themeStorage', () => ({
  cloudGet: vi.fn(async () => cloud.value),
  cloudSet: (k: string, v: string) => {
    cloud.set(k, v)
    return Promise.resolve()
  },
}))
vi.mock('../telegram/telegramChrome', () => ({ applyTelegramChrome: chrome.apply }))

const local = new Map<string, string>()

async function freshStore() {
  vi.resetModules()
  return import('./themeStore')
}

beforeEach(() => {
  local.clear()
  cloud.value = null
  cloud.set.mockClear()
  chrome.apply.mockClear()
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => local.get(k) ?? null,
    setItem: (k: string, v: string) => void local.set(k, v),
  })
  vi.stubGlobal('document', { documentElement: { dataset: {} as Record<string, string> } })
})

describe('themeStore', () => {
  it('defaults to dark on first launch', async () => {
    const { useThemeStore } = await freshStore()
    expect(useThemeStore.getState().theme).toBe('dark')
  })

  it('ignores garbage in storage', async () => {
    local.set('app-theme', 'purple')
    const { useThemeStore } = await freshStore()
    expect(useThemeStore.getState().theme).toBe('dark')
  })

  it('persists a choice and restores it after restart', async () => {
    const first = await freshStore()
    first.useThemeStore.getState().setTheme('light')
    expect(local.get('app-theme')).toBe('light')
    expect(cloud.set).toHaveBeenCalledWith('app-theme', 'light')
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(chrome.apply).toHaveBeenCalledWith('light')

    const second = await freshStore()
    expect(second.useThemeStore.getState().theme).toBe('light')
  })

  it('hydrate adopts the CloudStorage value and applies it', async () => {
    cloud.value = 'light'
    const { useThemeStore } = await freshStore()
    await useThemeStore.getState().hydrate()
    expect(useThemeStore.getState().theme).toBe('light')
    expect(local.get('app-theme')).toBe('light')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('hydrate without cloud value keeps current theme and applies it', async () => {
    const { useThemeStore } = await freshStore()
    await useThemeStore.getState().hydrate()
    expect(useThemeStore.getState().theme).toBe('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(chrome.apply).toHaveBeenCalledWith('dark')
  })

  it('QA m3-1 (bug): a choice made while CloudStorage is still loading is not overwritten by the late cloud value', async () => {
    cloud.value = 'dark'
    let release: () => void = () => {}
    const { useThemeStore } = await freshStore()
    const { cloudGet } = await import('../telegram/themeStorage')
    vi.mocked(cloudGet).mockImplementationOnce(
      () => new Promise((resolve) => { release = () => resolve('dark') }),
    )
    const hydrating = useThemeStore.getState().hydrate()
    useThemeStore.getState().setTheme('light') // user taps «Светлая» before the cloud answered
    release()
    await hydrating
    expect(useThemeStore.getState().theme).toBe('light')
    expect(document.documentElement.dataset.theme).toBe('light')
  })
})
