export const LAST_LANGUAGE_KEY = 'last_language'

type Lang = 'ru' | 'uz'
const isLang = (v: string | null | undefined): v is Lang => v === 'ru' || v === 'uz'

/** Language before /me answers: last known one, else Telegram language_code (uz -> uz), else ru. */
export function pickStartLanguage(stored: string | null, telegramCode: string | null): Lang {
  if (isLang(stored)) return stored
  return telegramCode?.toLowerCase().startsWith('uz') ? 'uz' : 'ru'
}

export function rememberLanguage(
  storage: Pick<Storage, 'setItem'> | null,
  language: string,
): void {
  if (!isLang(language)) return
  try {
    storage?.setItem(LAST_LANGUAGE_KEY, language)
  } catch {
    // private mode: next start just falls back to Telegram's language
  }
}

/** `language_code` of the user inside Telegram initData (tgWebAppData in the launch hash). */
export function readTelegramLanguageCode(hash: string): string | null {
  try {
    const data = new URLSearchParams(hash.replace(/^#/, '')).get('tgWebAppData')
    const user = data ? new URLSearchParams(data).get('user') : null
    const code = user ? (JSON.parse(user) as { language_code?: unknown }).language_code : null
    return typeof code === 'string' ? code : null
  } catch {
    return null
  }
}

function safeStorage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage
  } catch {
    return null
  }
}

export function detectStartLanguage(): Lang {
  const storage = safeStorage()
  let stored: string | null = null
  try {
    stored = storage?.getItem(LAST_LANGUAGE_KEY) ?? null
  } catch {
    stored = null
  }
  const hash = typeof window === 'undefined' ? '' : window.location.hash
  return pickStartLanguage(stored, readTelegramLanguageCode(hash))
}

export function rememberLanguageInBrowser(language: string): void {
  rememberLanguage(safeStorage(), language)
}
