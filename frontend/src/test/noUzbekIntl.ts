import { vi } from 'vitest'

/**
 * Makes Intl behave like Chromium inside an Android WebView / Telegram Desktop, which has no
 * Uzbek month names: for any `uz` locale a month comes out as the raw «M11». Node has full ICU
 * and would hide a bug that only shows on those devices.
 */
export function stubIntlWithoutUzbekMonths(): void {
  const Real = Intl.DateTimeFormat
  function NoUzbek(locales?: string | string[], options?: Intl.DateTimeFormatOptions) {
    const real = new Real(locales, options)
    const wanted = String(Array.isArray(locales) ? locales[0] : (locales ?? '')).toLowerCase()
    if (!(wanted.startsWith('uz') && options?.month)) return real
    const rawMonth = (date?: Date | number) => `M${new Date(date ?? Date.now()).getUTCMonth() + 1}`
    return {
      format: rawMonth,
      formatToParts: (date?: Date | number) => [{ type: 'month', value: rawMonth(date) }],
      resolvedOptions: () => real.resolvedOptions(),
    }
  }
  vi.stubGlobal('Intl', { ...Intl, DateTimeFormat: NoUzbek })
}
