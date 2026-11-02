import { on, postEvent, themeParams } from '@tma.js/sdk-react'

import { parseScheme, schemeFromBgColor, schemeFromLaunchParams, type Theme } from '../store/themeMode'

type WebAppLike = {
  colorScheme?: unknown
  onEvent?: (name: string, cb: () => void) => void
  offEvent?: (name: string, cb: () => void) => void
}

function webApp(): WebAppLike | null {
  if (typeof window === 'undefined') return null
  return (window as unknown as { Telegram?: { WebApp?: WebAppLike } }).Telegram?.WebApp ?? null
}

/**
 * Last scheme announced by Telegram over the Mini Apps bridge (theme_changed). Not using
 * themeParams.mount(): mounting it makes the SDK push header/background colours to the client,
 * which the owner forbids.
 */
let bridgeScheme: Theme | null = null
const bridgeListeners = new Set<() => void>()
try {
  on('theme_changed', (payload: { theme_params?: { bg_color?: unknown } }) => {
    bridgeScheme = schemeFromBgColor(payload?.theme_params?.bg_color) ?? bridgeScheme
    bridgeListeners.forEach((cb) => cb())
  })
} catch {
  // no SDK bridge (tests, plain browser)
}

/**
 * Asks the Telegram client for the current theme over the Mini Apps bridge; the answer arrives as
 * theme_changed (handled above). Does not touch window.Telegram.WebApp (the app does not load
 * telegram-web-app.js) and never sets header/background colours.
 */
export function requestTelegramTheme(): void {
  try {
    postEvent('web_app_request_theme')
  } catch {
    // no bridge (plain browser)
  }
}

/** Telegram colorScheme; falls back to the SDK theme params (background colour). Null outside Telegram. */
export function readTelegramScheme(): Theme | null {
  const direct = parseScheme(webApp()?.colorScheme)
  if (direct) return direct
  if (bridgeScheme) return bridgeScheme
  try {
    const state = themeParams.state() as { bgColor?: unknown } | undefined
    const fromState = schemeFromBgColor(state?.bgColor)
    if (fromState) return fromState
  } catch {
    // SDK not initialised
  }
  try {
    if (typeof window === 'undefined') return null
    return (
      schemeFromLaunchParams(window.location.hash) ??
      schemeFromLaunchParams(window.sessionStorage.getItem('tapps/launchParams'))
    )
  } catch {
    return null
  }
}

export function readMediaScheme(): Theme | null {
  try {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return null
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  } catch {
    return null
  }
}

/**
 * Calls onChange whenever the system scheme may have changed: Telegram themeChanged, the SDK theme
 * params, the browser media query, and every return to the app (visibility, focus, pageshow, Telegram
 * activated). The caller re-reads the scheme, so a missed event is repaired on the next return.
 */
export function watchSystemScheme(onChange: () => void): () => void {
  const stops: Array<() => void> = []
  // Every return to the app also asks the client for the current theme; the reply (theme_changed)
  // reaches onChange through bridgeListeners, so the request itself is not an onChange trigger.
  const onReturn = () => {
    requestTelegramTheme()
    onChange()
  }
  const app = webApp()
  if (app?.onEvent && app.offEvent) {
    app.onEvent('themeChanged', onChange)
    stops.push(() => app.offEvent?.('themeChanged', onChange))
    app.onEvent('activated', onReturn)
    stops.push(() => app.offEvent?.('activated', onReturn))
  }
  bridgeListeners.add(onChange)
  stops.push(() => bridgeListeners.delete(onChange))
  if (typeof document !== 'undefined') {
    const onVisible = () => {
      if (document.visibilityState !== 'hidden') onReturn()
    }
    document.addEventListener('visibilitychange', onVisible)
    stops.push(() => document.removeEventListener('visibilitychange', onVisible))
  }
  if (typeof window !== 'undefined') {
    for (const name of ['focus', 'pageshow']) {
      window.addEventListener(name, onReturn)
      stops.push(() => window.removeEventListener(name, onReturn))
    }
    try {
      const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
      if (mq?.addEventListener) {
        mq.addEventListener('change', onChange)
        stops.push(() => mq.removeEventListener('change', onChange))
      }
    } catch {
      // no matchMedia
    }
  }
  return () => stops.forEach((stop) => stop())
}
