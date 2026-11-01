import { init, miniApp } from '@tma.js/sdk-react'

/**
 * The app draws its own palette (dark by default), so Telegram theme params are
 * deliberately NOT bound to CSS variables. Only the SDK and miniApp are mounted
 * (Telegram client colours are left to Telegram; never call set*Color).
 */
export function bindTelegramThemeParams(): () => void {
  init()
  try {
    if (miniApp.mount.isAvailable() && !miniApp.isMounted()) miniApp.mount()
  } catch {
    // outside Telegram
  }
  return () => {
    try {
      miniApp.unmount()
    } catch {
      // ignore
    }
  }
}
