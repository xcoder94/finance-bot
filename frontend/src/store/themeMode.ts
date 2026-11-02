/** Pure theme-mode logic: the stored preference (System / Light / Dark) and the resolved appearance. */

export type Theme = 'dark' | 'light'
export type ThemePreference = 'system' | Theme

export const DEFAULT_PREFERENCE: ThemePreference = 'system'
/** Used only when neither Telegram nor the browser says anything about the scheme. */
export const FALLBACK_THEME: Theme = 'dark'

export function parsePreference(value: unknown): ThemePreference | null {
  return value === 'system' || value === 'dark' || value === 'light' ? value : null
}

export function parseScheme(value: unknown): Theme | null {
  return value === 'dark' || value === 'light' ? value : null
}

/** "System" follows the detected scheme; an explicit choice wins. */
export function resolveTheme(preference: ThemePreference, system: Theme | null): Theme {
  if (preference === 'dark' || preference === 'light') return preference
  return system ?? FALLBACK_THEME
}

/** Same luminance rule Telegram uses for colorScheme: dark when the background is dark. */
export function schemeFromBgColor(color: unknown): Theme | null {
  if (typeof color !== 'string') return null
  const m = /^#?([0-9a-f]{6})$/i.exec(color.trim()) ?? /^#?([0-9a-f]{3})$/i.exec(color.trim())
  if (!m) return null
  const hex = m[1].length === 3 ? m[1].replace(/./g, (c) => c + c) : m[1]
  const r = parseInt(hex.slice(0, 2), 16)
  const g = parseInt(hex.slice(2, 4), 16)
  const b = parseInt(hex.slice(4, 6), 16)
  return 0.299 * r + 0.587 * g + 0.114 * b < 128 ? 'dark' : 'light'
}

export type SchemeSources = {
  /** Telegram colorScheme (or derived from its theme params); null outside Telegram. */
  telegram: () => Theme | null
  /** prefers-color-scheme; null when unsupported. */
  media: () => Theme | null
}

/** System scheme = Telegram's, outside Telegram = the browser's. */
export function detectSystemScheme(sources: SchemeSources): Theme | null {
  return sources.telegram() ?? sources.media()
}

/** Scheme from Telegram launch params ("tgWebAppThemeParams=<json>" in the URL hash / session storage). */
export function schemeFromLaunchParams(raw: string | null | undefined): Theme | null {
  if (!raw) return null
  try {
    const value = new URLSearchParams(raw.replace(/^#/, '')).get('tgWebAppThemeParams')
    return value ? schemeFromBgColor((JSON.parse(value) as { bg_color?: unknown }).bg_color) : null
  } catch {
    return null
  }
}
