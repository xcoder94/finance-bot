import { create } from 'zustand'

import { applyTelegramChrome } from '../telegram/telegramChrome'
import { cloudGet, cloudSet } from '../telegram/themeStorage'

export type Theme = 'dark' | 'light'

export const THEME_STORAGE_KEY = 'app-theme'
export const DEFAULT_THEME: Theme = 'dark'

export function parseTheme(value: unknown): Theme | null {
  return value === 'dark' || value === 'light' ? value : null
}

function readLocal(): Theme | null {
  try {
    return parseTheme(localStorage.getItem(THEME_STORAGE_KEY))
  } catch {
    return null
  }
}

function writeLocal(theme: Theme): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    // storage unavailable
  }
}

function applyToDocument(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  applyTelegramChrome(theme)
}

type ThemeStore = {
  theme: Theme
  setTheme: (theme: Theme) => void
  /** Reconcile with Telegram CloudStorage (source of truth across devices). */
  hydrate: () => Promise<void>
}

/** Set when the user picks a theme; a late CloudStorage answer must not override it. */
let userChose = false

export const useThemeStore = create<ThemeStore>((set, get) => ({
  theme: readLocal() ?? DEFAULT_THEME,
  setTheme: (theme) => {
    userChose = true
    set({ theme })
    applyToDocument(theme)
    writeLocal(theme)
    void cloudSet(THEME_STORAGE_KEY, theme)
  },
  hydrate: async () => {
    userChose = false
    const cloud = parseTheme(await cloudGet(THEME_STORAGE_KEY))
    if (!userChose && cloud && cloud !== get().theme) {
      set({ theme: cloud })
      writeLocal(cloud)
    }
    applyToDocument(get().theme)
  },
}))
