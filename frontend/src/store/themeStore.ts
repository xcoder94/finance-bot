import { create } from 'zustand'

import { readMediaScheme, readTelegramScheme, watchSystemScheme } from '../telegram/colorScheme'
import { cloudGet, cloudSet } from '../telegram/themeStorage'
import {
  DEFAULT_PREFERENCE,
  detectSystemScheme,
  parsePreference,
  resolveTheme,
  type Theme,
  type ThemePreference,
} from './themeMode'

export type { Theme, ThemePreference }

/** The existing key; before dev-fix11 it held 'dark' | 'light' (always an explicit choice). */
export const THEME_STORAGE_KEY = 'app-theme'
export const DEFAULT_THEME: Theme = 'dark'

export function parseTheme(value: unknown): ThemePreference | null {
  return parsePreference(value)
}

function readLocal(): ThemePreference | null {
  try {
    return parsePreference(localStorage.getItem(THEME_STORAGE_KEY))
  } catch {
    return null
  }
}

function writeLocal(preference: ThemePreference): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, preference)
  } catch {
    // storage unavailable
  }
}

function applyToDocument(theme: Theme): void {
  document.documentElement.dataset.theme = theme
}

function detectSystem(): Theme | null {
  return detectSystemScheme({ telegram: readTelegramScheme, media: readMediaScheme })
}

type ThemeStore = {
  /** What the user picked: system (default) | light | dark. */
  preference: ThemePreference
  /** Detected Telegram / browser scheme. */
  systemTheme: Theme | null
  /** Resolved appearance actually drawn. */
  theme: Theme
  setPreference: (preference: ThemePreference) => void
  /** Kept for callers that pick a concrete theme. */
  setTheme: (theme: Theme) => void
  /** Re-read the system scheme (themeChanged, return from background). */
  refreshSystem: () => void
  /** Follow Telegram / OS scheme changes; returns the unsubscribe. */
  watchSystem: () => () => void
  /** Reconcile with Telegram CloudStorage (source of truth across devices). */
  hydrate: () => Promise<void>
}

/** Set when the user picks a theme; a late CloudStorage answer must not override it. */
let userChose = false

function derive(preference: ThemePreference, systemTheme: Theme | null) {
  return { preference, systemTheme, theme: resolveTheme(preference, systemTheme) }
}

const initialSystem = detectSystem()
const initialPreference = readLocal() ?? DEFAULT_PREFERENCE

export const useThemeStore = create<ThemeStore>((set, get) => ({
  ...derive(initialPreference, initialSystem),
  setPreference: (preference) => {
    userChose = true
    const next = derive(preference, detectSystem())
    set(next)
    applyToDocument(next.theme)
    writeLocal(preference)
    void cloudSet(THEME_STORAGE_KEY, preference)
  },
  setTheme: (theme) => get().setPreference(theme),
  refreshSystem: () => {
    const next = derive(get().preference, detectSystem())
    if (next.theme !== get().theme || next.systemTheme !== get().systemTheme) set(next)
    applyToDocument(next.theme)
  },
  watchSystem: () => {
    get().refreshSystem()
    return watchSystemScheme(() => get().refreshSystem())
  },
  hydrate: async () => {
    userChose = false
    const cloud = parsePreference(await cloudGet(THEME_STORAGE_KEY))
    if (!userChose && cloud && cloud !== get().preference) {
      set(derive(cloud, detectSystem()))
      writeLocal(cloud)
    }
    applyToDocument(get().theme)
  },
}))
