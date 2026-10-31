import { miniApp } from '@tma.js/sdk-react'

import type { Theme } from '../store/themeStore'

export const CHROME_COLORS: Record<Theme, `#${string}`> = {
  dark: '#17212b',
  light: '#ffffff',
}

/** Telegram header/background follow the chosen in-app theme. */
export function applyTelegramChrome(theme: Theme): void {
  const color = CHROME_COLORS[theme]
  try {
    if (miniApp.setHeaderColor.isAvailable()) miniApp.setHeaderColor(color)
    if (miniApp.setBgColor.isAvailable()) miniApp.setBgColor(color)
  } catch {
    // outside Telegram or unsupported client version
  }
}
