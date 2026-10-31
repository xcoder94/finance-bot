export type InitDataUser = {
  firstName: string | null
  lastName: string | null
  photoUrl: string | null
}

const EMPTY: InitDataUser = { firstName: null, lastName: null, photoUrl: null }

function httpsUrl(value: unknown): string | null {
  const v = str(value)
  if (!v) {
    return null
  }
  try {
    return new URL(v).protocol === 'https:' ? v : null
  } catch {
    return null
  }
}

function str(value: unknown): string | null {
  return typeof value === 'string' && value.trim() !== '' ? value.trim() : null
}

/** Reads user.first_name / last_name / photo_url from raw Telegram initData. */
export function parseInitDataUser(rawInitData: string | undefined | null): InitDataUser {
  if (!rawInitData) {
    return EMPTY
  }
  try {
    const rawUser = new URLSearchParams(rawInitData).get('user')
    if (!rawUser) {
      return EMPTY
    }
    const user = JSON.parse(rawUser) as Record<string, unknown>
    return {
      firstName: str(user.first_name),
      lastName: str(user.last_name),
      photoUrl: httpsUrl(user.photo_url),
    }
  } catch {
    return EMPTY
  }
}

/** First + last name initials, else first letter of first name, else "?". */
export function userInitials(firstName: string | null, lastName: string | null): string {
  const first = Array.from(firstName?.trim() ?? '')[0]
  const last = Array.from(lastName?.trim() ?? '')[0]
  if (first && last) {
    return (first + last).toUpperCase()
  }
  return (first ?? '?').toUpperCase()
}

/** Where "‹ Главная" on Settings leads: the page we came from, else Home. */
export function settingsBackTarget(state: unknown): string {
  const from = (state as { from?: unknown } | null)?.from
  return typeof from === 'string' && from.startsWith('/') && !/^\/[/\\]/.test(from) && !from.startsWith('/settings')
    ? from
    : '/'
}
