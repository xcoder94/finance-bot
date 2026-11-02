// Real client path: no window.Telegram.WebApp, only the Mini Apps bridge (@tma.js). Checked on the bridge mock.
import { beforeEach, describe, expect, it, vi } from 'vitest'

const posted: string[] = []
const handlers = new Map<string, (payload: unknown) => void>()
vi.mock('@tma.js/sdk-react', () => ({
  on: (name: string, cb: (payload: unknown) => void) => void handlers.set(name, cb),
  postEvent: (name: string) => void posted.push(name),
  themeParams: { state: () => undefined },
}))

type Listener = () => void
function fakeWindow() {
  const listeners = new Map<string, Listener[]>()
  const add = (n: string, cb: Listener) => listeners.set(n, [...(listeners.get(n) ?? []), cb])
  const fire = (n: string) => (listeners.get(n) ?? []).forEach((cb) => cb())
  const win: Record<string, unknown> & { sessionStorage: { getItem: () => string | null } } = {
    addEventListener: add,
    removeEventListener: () => {},
    matchMedia: () => ({ matches: true, addEventListener: () => {}, removeEventListener: () => {} }),
    sessionStorage: { getItem: () => null },
    location: { hash: '' },
  }
  const doc = { visibilityState: 'visible' as string, addEventListener: add, removeEventListener: () => {} }
  return { win, doc, fire }
}

describe('colorScheme over the bridge', () => {
  beforeEach(() => {
    posted.length = 0
    vi.resetModules()
    handlers.clear()
  })

  it('asks the client for the theme on every return, never colours the header', async () => {
    const { win, doc, fire } = fakeWindow()
    vi.stubGlobal('window', win)
    vi.stubGlobal('document', doc)
    const { watchSystemScheme } = await import('./colorScheme')
    const changes = vi.fn()
    watchSystemScheme(changes)
    for (const ev of ['visibilitychange', 'focus', 'pageshow']) {
      posted.length = 0
      fire(ev)
      expect(posted, ev).toEqual(['web_app_request_theme'])
    }
    expect(posted.some((n) => /set_(header|background|bottom_bar)_color/.test(n))).toBe(false)
    vi.unstubAllGlobals()
  })

  it('does not ask while hidden', async () => {
    const { win, doc, fire } = fakeWindow()
    doc.visibilityState = 'hidden'
    vi.stubGlobal('window', win)
    vi.stubGlobal('document', doc)
    const { watchSystemScheme } = await import('./colorScheme')
    watchSystemScheme(() => {})
    fire('visibilitychange')
    expect(posted).toEqual([])
    vi.unstubAllGlobals()
  })

  it('applies the theme_changed answer without asking again (no loop)', async () => {
    const { win, doc } = fakeWindow()
    vi.stubGlobal('window', win)
    vi.stubGlobal('document', doc)
    const { watchSystemScheme, readTelegramScheme } = await import('./colorScheme')
    const changes = vi.fn()
    watchSystemScheme(changes)
    handlers.get('theme_changed')?.({ theme_params: { bg_color: '#ffffff' } })
    expect(readTelegramScheme()).toBe('light')
    expect(changes).toHaveBeenCalledTimes(1)
    expect(posted).toEqual([])
    handlers.get('theme_changed')?.({ theme_params: { bg_color: '#17212b' } })
    expect(readTelegramScheme()).toBe('dark')
    vi.unstubAllGlobals()
  })

  it('quoted sessionStorage launch params decide the scheme when nothing else is known', async () => {
    const { win, doc } = fakeWindow()
    const tp = `tgWebAppThemeParams=${encodeURIComponent(JSON.stringify({ bg_color: '#ffffff' }))}`
    win.sessionStorage = { getItem: () => JSON.stringify(`tgWebAppVersion=8.0&${tp}`) }
    vi.stubGlobal('window', win)
    vi.stubGlobal('document', doc)
    const { readTelegramScheme } = await import('./colorScheme')
    expect(readTelegramScheme()).toBe('light')
    vi.unstubAllGlobals()
  })
})
